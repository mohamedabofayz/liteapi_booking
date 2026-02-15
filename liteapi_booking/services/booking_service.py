import json
import logging
from odoo import models, api, _, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class BookingService(models.AbstractModel):
    _name = 'liteapi.booking.service'
    _description = 'LiteAPI Booking Logic'

    @api.model
    def execute_prebook_api(self, offer_id):
        """
        تنفيذ طلب Prebook.
        هام: تم إزالة currency و guestNationality لأنها تسبب خطأ 4002 (Wrong Input).
        واجهة LiteAPI v3 تطلب فقط offerId و usePaymentSdk في هذه المرحلة.
        """
        if not offer_id:
            raise UserError(_("Offer ID is missing."))

        client = self.env['liteapi.client']
        
        # تنظيف المعرف من أي مسافات زائدة
        clean_offer_id = str(offer_id).strip()

        # إعداد البيانات الصحيحة (فقط الحقول المطلوبة)
        payload = {
            "offerId": clean_offer_id,
            "usePaymentSdk": True
        }

        try:
            _logger.info(f"⚡ PREBOOK PAYLOAD: {json.dumps(payload)}")
            
            response = client.make_request('/rates/prebook', method='POST', json=payload)
            data = response.get('data', {}) if isinstance(response, dict) else response
            
            prebook_id = data.get('prebookId')
            transaction_id = data.get('transactionId')
            secret_key = data.get('secretKey') or data.get('secretkey')

            if not prebook_id or not transaction_id:
                _logger.error(f"Prebook Response Missing Keys: {data}")
                raise UserError(_("Gateway Error: Missing transaction parameters from LiteAPI."))

            return {
                'prebookId': prebook_id,
                'transactionId': transaction_id,
                'secretKey': secret_key
            }

        except Exception as e:
            _logger.error(f"❌ Prebook Failed. OfferID: {clean_offer_id[:20]}... Error: {e}")
            raise UserError(_("Payment Init Error: %s") % str(e))

    @api.model
    def finalize_booking_api(self, prebook_id, transaction_id, guest_info):
        """تثبيت الحجز النهائي وإنشاء السجلات"""
        client = self.env['liteapi.client']
        
        payload = {
            "prebookId": prebook_id,
            "payment": {
                "method": "TRANSACTION_ID",
                "transactionId": transaction_id
            },
            "holder": {
                "firstName": guest_info.get('first_name', 'Guest'),
                "lastName": guest_info.get('last_name', 'User'),
                "email": guest_info.get('email'),
            },
            "guests": [
                {
                    "occupancyNumber": 1,
                    "firstName": guest_info.get('first_name', 'Guest'),
                    "lastName": guest_info.get('last_name', 'User'),
                    "email": guest_info.get('email')
                }
            ],
            "clientReference": f"WEB-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}" 
        }

        try:
            response = client.make_request('/rates/book', method='POST', json=payload)
            data = response.get('data', {}) if isinstance(response, dict) else response
            
            booking_ref = data.get('bookingId') or data.get('id')
            
            if data.get('status') == 'FAILED' or not booking_ref:
                 msg = data.get('error', {}).get('message', 'Unknown Error')
                 raise UserError(f"Booking Failed: {msg}")

            # 1. العثور على العميل أو إنشاؤه
            email = guest_info.get('email')
            Partner = self.env['res.partner'].sudo()
            partner = Partner.search([('email', '=', email)], limit=1)
            if not partner:
                partner = Partner.create({
                    'name': f"{guest_info.get('first_name')} {guest_info.get('last_name')}",
                    'email': email,
                    'type': 'contact'
                })

            # 2. تجهيز البيانات
            hotel_lite_id = data.get('hotelId')
            hotel = self.env['liteapi.hotel'].sudo().search([('liteapi_hotel_id', '=', hotel_lite_id)], limit=1)
            price_total = data.get('price', {}).get('amount', 0.0)

            # 3. إنشاء أمر البيع
            product = self.env['product.product'].sudo().search([('name', '=', 'Hotel Booking Service')], limit=1)
            if not product:
                product = self.env['product.product'].sudo().create({'name': 'Hotel Booking Service', 'type': 'service'})

            sale_order = self.env['sale.order'].sudo().create({
                'partner_id': partner.id,
                'state': 'sale',
                'liteapi_prebook_id': prebook_id,
                'liteapi_transaction_id': transaction_id
            })

            self.env['sale.order.line'].sudo().create({
                'order_id': sale_order.id,
                'product_id': product.id,
                'name': f"Hotel Booking: {data.get('hotelName')}",
                'product_uom_qty': 1,
                'price_unit': price_total,
                'liteapi_hotel_id': hotel.id if hotel else False,
            })

            # 4. إنشاء سجل الحجز
            booking = self.env['liteapi.booking'].sudo().create({
                'partner_id': partner.id,
                'sale_order_id': sale_order.id,
                'hotel_id': hotel.id if hotel else False,
                'room_type': data.get('roomName'),
                'checkin_date': data.get('checkin'),
                'checkout_date': data.get('checkout'),
                'liteapi_booking_id': booking_ref,
                'status': 'confirmed',
                'booking_details': json.dumps(data)
            })

            return booking

        except Exception as e:
            _logger.exception("Booking Finalize Logic Failed")
            raise UserError(f"Booking Finalization Error: {str(e)}")