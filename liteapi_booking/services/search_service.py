import json
import logging
from datetime import datetime, timedelta
from odoo import models, api, fields, _
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

class SearchService(models.AbstractModel):
    _name = 'liteapi.search.service'
    _description = 'LiteAPI Search Handler'

    @api.model
    def search_hotels(self, search_type, search_value, checkin, checkout, guests):
        user_lang = self.env.context.get('lang') or self.env.user.lang or 'en_US'
        api_lang_code = user_lang[:2] 

        # مفتاح البحث للكاش
        cache_key = f"{search_type}|{search_value}|{checkin}|{checkout}|{guests}|{user_lang}"
        
        # 1. محاولة جلب كاش "طازج" (ساري المفعول - دقيقة واحدة)
        cached_result = self._get_from_cache(cache_key, expired=False)
        if cached_result:
            return json.loads(cached_result)

        # 2. إذا لم يوجد، نطلب من API (البحث الكامل للحصول على الصور والتفاصيل)
        return self._fetch_from_api_and_cache(
            search_type, search_value, checkin, checkout, guests, cache_key, 
            api_lang_code, user_lang
        )

    @api.model
    def _get_from_cache(self, cache_key, expired=False):
        """
        جلب الكاش.
        expired=False: يجلب فقط الساري (لمنع التكرار في نفس الدقيقة).
        expired=True: يجلب أحدث سجل حتى لو منتهي (للاستخدام عند فشل الـ API).
        """
        domain = [('cache_key', '=', cache_key)]
        if not expired:
            domain.append(('expires_at', '>', fields.Datetime.now()))
            
        # ترتيب تنازلي لضمان جلب الأحدث دائماً
        cache_entry = self.env['liteapi.search.cache'].search(domain, order='create_date desc', limit=1)
        return cache_entry.response_json if cache_entry else False

    # ==================================================================================
    # [NEW] دالة البحث السريع باستخدام min-rates (آلية الحصول على offerId الخفيفة)
    # ==================================================================================
    @api.model
    def fetch_min_rates_api(self, hotel_ids, checkin, checkout, guests, currency="SAR"):
        """
        تنفيذ طلب min-rates للحصول على offerId والسعر فقط (بدون صور أو وصف).
        تستخدم هذه الدالة عندما يكون لديك Hotel IDs وتريد أسرع رد للحجز.
        """
        client = self.env['liteapi.client']
        
        # تجهيز البيانات حسب مواصفات min-rates
        payload = {
            "checkin": str(checkin),
            "checkout": str(checkout),
            "currency": currency,
            "guestNationality": "SA", # يمكن جعلها ديناميكية لاحقاً
            "timeout": 10,
            "hotelIds": hotel_ids, # يجب أن تكون قائمة List of Strings
            "occupancies": [{ "adults": int(guests) }]
        }

        try:
            # إرسال الطلب إلى min-rates
            # تأكد من إضافة '/hotels/min-rates' في قائمة ALLOWED_ENDPOINTS في liteapi_client.py
            response_data = client.make_request('/hotels/min-rates', method='POST', json=payload)
            data = response_data.get('data', [])
            
            results = {}
            for item in data:
                hotel_lite_id = item.get('hotelId')
                if hotel_lite_id:
                    results[hotel_lite_id] = {
                        'hotel_lite_id': hotel_lite_id,
                        'offer_id': item.get('offerId'), # هذا هو المطلوب لخطوة prebook
                        'price': item.get('price'),
                        'currency': currency,
                        'ssp': item.get('suggestedSellingPrice')
                    }
            return results

        except Exception as e:
            _logger.error(f"Min-Rates Search Error: {e}")
            return {}

    # ==================================================================================
    # دالة البحث الكامل (تجلب الصور والوصف + offerId) - تستخدم لصفحة النتائج
    # ==================================================================================
    @api.model
    def _fetch_from_api_and_cache(self, search_type, search_value, checkin, checkout, guests, cache_key, api_lang, full_lang_code):
        client = self.env['liteapi.client']
        
        payload = {
            "occupancies": [{"adults": int(guests)}],
            "checkin": str(checkin),
            "checkout": str(checkout),
            "currency": "SAR",
            "guestNationality": "SA",
            "roomMapping": True,
            "language": api_lang 
        }

        # تحديد نوع البحث وتجهيز Payload
        if search_type == 'vibe' or search_type == 'place':
            payload['aiSearch'] = search_value
        else:
            if not search_value: return {'hotels': []}
            if str(search_value).isdigit():
                # بحث بالمدينة: نجلب الفنادق المحلية المرتبطة بالمدينة لإرسال معرفاتها
                city = self.env['liteapi.city'].browse(int(search_value))
                if not city.exists(): return {'hotels': []}
                local_hotels = self.env['liteapi.hotel'].search([('city_id', '=', city.id)])
                hotel_ids = [str(h.liteapi_hotel_id) for h in local_hotels if h.liteapi_hotel_id]
                if not hotel_ids: return {'hotels': []}
                payload['hotelIds'] = hotel_ids[:100] # API limits often apply
            else:
                payload['aiSearch'] = str(search_value)

        try:
            # محاولة الاتصال بالـ API (Full Rates Endpoint)
            response_data = client.make_request('/hotels/rates', method='POST', json=payload)
            hotels_list = []
            api_data = response_data.get('data', [])
            
            # إذا الرد فارغ
            if not api_data: 
                # [Fallback] نحاول العودة للكاش القديم إذا كانت النتائج فارغة
                stale_cache = self._get_from_cache(cache_key, expired=True)
                if stale_cache:
                    _logger.warning(f"⚠️ API returned empty data. Using stale cache for {cache_key}")
                    return json.loads(stale_cache)
                return {'hotels': []}

            # معالجة البيانات
            for item in api_data:
                hotel_lite_id = item.get('hotelId') or item.get('id')
                if not hotel_lite_id: continue

                lowest_price = 0.0
                rates = item.get('rates', []) or []
                
                # التعامل مع اختلاف هيكلية الرد في بعض الحالات
                if not rates and item.get('roomTypes'):
                     for rt in item.get('roomTypes'):
                         rates.extend(rt.get('rates', []))
                
                if rates:
                    prices = [
                        r.get('retailPrice', {}).get('amount') or 
                        r.get('retailRate', {}).get('total', [{}])[0].get('amount') 
                        for r in rates
                    ]
                    prices = [p for p in prices if p]
                    if prices: lowest_price = min(prices)

                if lowest_price > 0:
                    local_hotel = self.env['liteapi.hotel'].search([('liteapi_hotel_id', '=', hotel_lite_id)], limit=1)
                    
                    api_desc = item.get('description') or item.get('hotelDescription') or ""
                    
                    # تحديث البيانات المحلية (الصور والوصف) إذا وجدت بيانات جديدة
                    if local_hotel:
                        vals = {}
                        if not local_hotel.image_url:
                            if item.get('main_photo'): vals['image_url'] = item.get('main_photo')
                            elif item.get('thumbnail'): vals['image_url'] = item.get('thumbnail')
                            elif item.get('hotelImages'): vals['image_url'] = item['hotelImages'][0].get('url')
                        
                        api_stars = int(float(item.get('starRating') or item.get('stars') or 0))
                        if local_hotel.star_rating == 0 and api_stars > 0:
                            vals['star_rating'] = api_stars

                        if api_desc:
                            vals['description'] = api_desc
                            local_hotel.sudo().with_context(lang=full_lang_code).write(vals)
                        elif vals:
                            local_hotel.sudo().write(vals)

                    # تجهيز صورة للعرض
                    image_url = '/web/static/src/img/placeholder.png'
                    if local_hotel and local_hotel.image_url:
                        image_url = local_hotel.image_url
                    elif item.get('main_photo'): image_url = item.get('main_photo')
                    elif item.get('thumbnail'): image_url = item.get('thumbnail')
                    
                    # تجهيز النجوم
                    star_rating = 0
                    if local_hotel and local_hotel.star_rating > 0:
                        star_rating = local_hotel.star_rating
                    else:
                        try: star_rating = int(float(item.get('starRating') or item.get('stars') or 0))
                        except: pass

                    # تجهيز الوصف المختصر
                    short_desc = ""
                    desc_source = api_desc
                    if not desc_source and local_hotel:
                        desc_source = local_hotel.with_context(lang=full_lang_code).description or ""
                    
                    if desc_source:
                        plain_text = html2plaintext(desc_source).strip()
                        if len(plain_text) > 150:
                            short_desc = plain_text[:147] + "..."
                        else:
                            short_desc = plain_text

                    hotels_list.append({
                        'id': local_hotel.id if local_hotel else 0,
                        'liteapi_id': hotel_lite_id,
                        'name': item.get('name') or (local_hotel.name if local_hotel else "Unknown Hotel"),
                        'price': lowest_price,
                        'currency': 'SAR',
                        'star_rating': star_rating,
                        'image_url': image_url,
                        'short_description': short_desc,
                        'address': item.get('address'),
                        'review_score': item.get('reviewScore') or item.get('score') or 0,
                        'taxes_included': True
                    })

            final_result = {'hotels': hotels_list}
            
            # حفظ الكاش الجديد (لمدة دقيقة ونصف)
            try:
                expiration_time = fields.Datetime.now() + timedelta(seconds=90)
                
                self.env['liteapi.search.cache'].create({
                    'cache_key': cache_key,
                    'city_id': int(search_value) if str(search_value).isdigit() else False,
                    'checkin_date': checkin,
                    'checkout_date': checkout,
                    'guests': guests,
                    'response_json': json.dumps(final_result),
                    'expires_at': expiration_time 
                })
            except Exception as e:
                _logger.warning(f"Cache Save Error: {e}")
            
            return final_result

        except Exception as e:
             _logger.error(f"Search Service Error (API Failed): {e}")
             
             # Fallback Strategy: استخدام الكاش القديم عند فشل الاتصال
             _logger.info("♻️ Attempting to use Stale Cache due to API failure...")
             stale_cache = self._get_from_cache(cache_key, expired=True)
             
             if stale_cache:
                 _logger.info(f"✅ Served Stale Cache for: {cache_key}")
                 return json.loads(stale_cache)
             
             return {'hotels': []}