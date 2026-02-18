import json
import logging
from odoo import models, api, _, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# رابط خدمات الحجز
BOOKING_BASE_URL = "https://book.liteapi.travel/v3.0"

class BookingService(models.AbstractModel):
    _name = 'liteapi.booking.service'
    _description = 'LiteAPI Booking Logic'

    @api.model
    def execute_prebook_api(self, offer_id, search_context=None):
        """
        تنفيذ طلب Prebook مع دعم إعادة المحاولة الذكية.
        """
        if not offer_id:
            raise UserError(_("Offer ID is missing."))

        client = self.env['liteapi.client']
        clean_offer_id = str(offer_id).strip()
        
        payload = {
            "usePaymentSdk": True,
            "offerId": clean_offer_id,
            "includeCreditBalance": False
        }
        
        query_params = {
            'timeout': '30',
            'includeCreditBalance': 'false'
        }

        try:
            _logger.info(f"⚡ PREBOOK REQUEST (Attempt 1): {json.dumps(payload)}")
            
            response = client.make_request(
                '/rates/prebook', 
                method='POST', 
                json=payload, 
                params=query_params,
                custom_base_url=BOOKING_BASE_URL
            )
            return self._parse_prebook_response(response)

        except Exception as e:
            error_msg = str(e)
            _logger.warning(f"⚠️ Prebook Failed: {error_msg}")
            
            # --- Smart Retry Logic ---
            # التحقق من أخطاء انتهاء الصلاحية (4002 أو 400 بشكل عام)
            if search_context and ('4002' in error_msg or 'invalid offerId' in error_msg.lower() or '400' in error_msg):
                _logger.info("🔄 Offer expired. Fetching FRESH offer via Refresh...")
                
                # جلب عرض جديد (هنا يحدث الخطأ سابقاً)
                new_offer_data = self._refresh_offer_id(search_context)
                
                if new_offer_data:
                    new_id = new_offer_data['offer_id']
                    _logger.info(f"✅ Found Fresh Offer: {new_id[:20]}... | Price: {new_offer_data['price']}")
                    
                    payload['offerId'] = new_id
                    
                    try:
                        _logger.info(f"⚡ PREBOOK REQUEST (Retry): {json.dumps(payload)}")
                        response = client.make_request(
                            '/rates/prebook', 
                            method='POST', 
                            json=payload, 
                            params=query_params,
                            custom_base_url=BOOKING_BASE_URL
                        )
                        result = self._parse_prebook_response(response)
                        
                        result.update({
                            'is_refreshed': True,
                            'new_offer_id': new_id,
                            'new_price': new_offer_data['price']
                        })
                        return result

                    except Exception as retry_e:
                        _logger.error(f"❌ Retry Failed: {retry_e}")
            
            if '4002' in error_msg or 'invalid offerId' in error_msg:
                raise UserError(_("عذراً، انتهت صلاحية هذا العرض. يرجى إعادة البحث للحصول على أحدث الأسعار."))
            
            raise UserError(_("Booking Error: %s") % error_msg)

    def _parse_prebook_response(self, data):
        resp_data = data.get('data', {}) if isinstance(data, dict) else data
        
        if not resp_data and 'prebookId' in data:
            resp_data = data

        prebook_id = resp_data.get('prebookId')
        
        if not prebook_id:
            _logger.error(f"Invalid Prebook Response: {data}")
            raise UserError(_("فشل في استلام رقم الحجز المبدئي (Prebook ID)."))

        return {
            'prebookId': prebook_id,
            'transactionId': resp_data.get('transactionId'),
            'secretKey': resp_data.get('secretKey'),
            'offerId': resp_data.get('offerId'),
            'price': resp_data.get('price'),
            'currency': resp_data.get('currency')
        }

    def _refresh_offer_id(self, ctx):
        """
        جلب عرض جديد مع معالجة آمنة للأسعار لتجنب أخطاء NoneType
        """
        try:
            client = self.env['liteapi.client']
            
            payload = {
                "hotelIds": [ctx.get('hotel_lite_id')],
                "occupancies": [{"adults": int(ctx.get('guests', 2))}],
                "checkin": str(ctx.get('checkin')),
                "checkout": str(ctx.get('checkout')),
                "currency": "SAR",
                "guestNationality": "SA",
                "roomMapping": True
            }
            
            # نستخدم سيرفر البحث للبحث عن الغرف
            resp = client.make_request('/hotels/rates', method='POST', json=payload)
            data = resp.get('data', [])
            
            target_price = float(str(ctx.get('price', 0)).replace(',', '').replace(' ', '') or 0)
            if target_price == 0: target_price = 1000.0

            all_rates = []

            if data:
                for room in data[0].get('roomTypes', []):
                    for rate in room.get('rates', []):
                        
                        # === [FIX START] استخراج السعر بشكل آمن جداً ===
                        price = 0.0
                        
                        # 1. محاولة استخراج retailPrice
                        retail_price_obj = rate.get('retailPrice')
                        if retail_price_obj and isinstance(retail_price_obj, dict):
                            price = float(retail_price_obj.get('amount') or 0)
                        
                        # 2. إذا لم نجد، نحاول استخراج retailRate -> total -> amount
                        if price == 0:
                            retail_rate_obj = rate.get('retailRate')
                            # التأكد من أن retailRate قاموس وليس None
                            if retail_rate_obj and isinstance(retail_rate_obj, dict):
                                total_list = retail_rate_obj.get('total')
                                # التأكد من أن total قائمة وليست فارغة
                                if total_list and isinstance(total_list, list) and len(total_list) > 0:
                                    first_total = total_list[0]
                                    if first_total and isinstance(first_total, dict):
                                        price = float(first_total.get('amount') or 0)
                        # === [FIX END] ===

                        if price > 0:
                            offer_info = {'offer_id': rate.get('offerId'), 'price': price}
                            all_rates.append(offer_info)
                            
                            # تطابق ذكي (فرق أقل من 10 ريال)
                            if abs(price - target_price) < 10.0:
                                return offer_info
            
            if all_rates:
                 _logger.warning("⚠️ No exact price match found during refresh. Using CHEAPEST available rate.")
                 all_rates.sort(key=lambda x: x['price'])
                 return all_rates[0]

            return None

        except Exception as e:
            _logger.error(f"Refresh Error: {e}")
            return None

    @api.model
    def finalize_booking_api(self, prebook_id, transaction_id, guest_info, booking_meta={}):
        """ تثبيت الحجز (Book) """
        client = self.env['liteapi.client']
        
        first_name = guest_info.get('first_name', 'Guest')
        last_name = guest_info.get('last_name', 'User')
        email = guest_info.get('email', 'guest@example.com')

        payload = {
            "prebookId": prebook_id,
            "payment": {
                "method": "TRANSACTION_ID",
                "transactionId": transaction_id
            },
            "holder": {
                "firstName": first_name,
                "lastName": last_name,
                "email": email,
            },
            "guests": [{
                "occupancyNumber": 1,
                "firstName": first_name,
                "lastName": last_name,
                "email": email
            }],
            "clientReference": f"REF-{fields.Datetime.now().strftime('%Y%m%d%H%M')}"
        }

        try:
            _logger.info(f"🚀 BOOK REQUEST: {json.dumps(payload)}")
            
            response = client.make_request(
                '/rates/book', 
                method='POST', 
                json=payload,
                custom_base_url=BOOKING_BASE_URL
            )
            data = response.get('data', {}) if isinstance(response, dict) else response
            
            if not data.get('bookingId'):
                 raise UserError(f"Booking Failed: {data.get('error') or 'Unknown error'}")

            self._create_odoo_booking(data, guest_info, booking_meta, prebook_id, transaction_id)
            return data

        except Exception as e:
            raise UserError(f"Finalize Booking Error: {str(e)}")

    def _create_odoo_booking(self, data, guest_info, booking_meta, prebook_id, transaction_id):
        email = guest_info.get('email')
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('email', '=', email)], limit=1)
        if not partner:
            partner = Partner.create({
                'name': f"{guest_info.get('first_name')} {guest_info.get('last_name')}",
                'email': email
            })

        self.env['liteapi.booking'].sudo().create({
            'partner_id': partner.id,
            'hotel_name': data.get('hotelName') or booking_meta.get('hotel_name'),
            'liteapi_booking_id': data.get('bookingId'),
            'prebook_id': prebook_id,
            'transaction_id': transaction_id,
            'status': 'confirmed',
            'price': data.get('price', {}).get('amount', 0),
            'currency': data.get('price', {}).get('currency', 'SAR'),
            'checkin_date': booking_meta.get('checkin'),
            'checkout_date': booking_meta.get('checkout'),
            'guest_name': partner.name,
            'email': email,
            'booking_details': json.dumps(data)
        })