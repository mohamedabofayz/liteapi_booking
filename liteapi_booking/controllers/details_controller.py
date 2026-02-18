from odoo import http, fields
from odoo.http import request
import logging
import json

try:
    from markupsafe import Markup
except ImportError:
    try:
        from odoo.tools import Markup
    except ImportError:
        def Markup(text): return text

_logger = logging.getLogger(__name__)

class LiteAPIDetailsController(http.Controller):

    @http.route(['/booking/view/<string:hotel_lite_id>'], type='http', auth="public", website=True)
    def hotel_details(self, hotel_lite_id, **kwargs):
        # 1. جلب بيانات الجلسة (للتواريخ والضيوف)
        search_params = request.session.get('liteapi_search')
        if not search_params:
             return request.redirect('/hotel/search')

        # 2. البحث عن الفندق محلياً (CMS Data)
        hotel = request.env['liteapi.hotel'].sudo().search([('liteapi_hotel_id', '=', hotel_lite_id)], limit=1)
        
        client = request.env['liteapi.client'].sudo()
        user_lang = request.env.context.get('lang', 'en_US')[:2]

        # 3. إعداد البيانات الافتراضية من المحلي (Local First)
        # هذا يضمن السرعة واستخدام المحتوى المخصص إذا وجد
        hotel_info = {
            'name': hotel.name if hotel else "Hotel Details",
            'address': getattr(hotel, 'name', '') or "",
            'rating': 0.0, 
            'review_count': 0, 
            'stars': hotel.star_rating if hotel else 0,
            'images': [hotel.image_url] if hotel and hotel.image_url else ['/web/static/src/img/placeholder.png'],
            'description': Markup(hotel.description) if hotel and hotel.description else "",
            'facilities': [], 
            'google_maps_link': "#"
        }

        # 4. جلب البيانات الحية من API ودمجها (Live Data Merge)
        try:
            d_resp = client.make_request('/data/hotel', method='GET', params={
                'hotelId': hotel_lite_id,
                'language': user_lang 
            })
            d_data = d_resp.get('data', {})
            
            if d_data:
                # -- استخراج البيانات من API --
                api_desc = d_data.get('description') or d_data.get('hotelDescription') or ""
                api_stars = int(d_data.get('starRating') or d_data.get('stars') or 0)
                api_imgs = [i['url'] for i in d_data.get('hotelImages', []) if i.get('url')]
                
                # -- منطق الدمج (CMS Logic) --
                # نستخدم البيانات المحلية إذا وجدت، وإلا نملأها من الـ API
                final_desc = hotel.description if (hotel and hotel.description) else api_desc
                final_images = [hotel.image_url] if (hotel and hotel.image_url) else (api_imgs if api_imgs else hotel_info['images'])
                
                hotel_info.update({
                    'name': d_data.get('name') or hotel_info['name'],
                    'address': d_data.get('address') or hotel_info['address'],
                    'rating': d_data.get('rating', 0.0),
                    'stars': api_stars if api_stars > 0 else hotel_info['stars'],
                    'description': Markup(final_desc),
                    'facilities': d_data.get('hotelFacilities', []) or hotel_info['facilities'],
                    'images': final_images
                })
                
                # -- تحديث الخريطة (Google Maps Fix) --
                lat = d_data.get('latitude')
                lon = d_data.get('longitude')
                if lat and lon:
                    # الرابط القياسي الصحيح الذي يعمل على جميع الأجهزة
                    hotel_info['google_maps_link'] = f"https://maps.google.com/?q={lat},{lon}"

                # -- تحديث الكاش المحلي (للمستقبل) --
                if hotel:
                    vals = {}
                    if not hotel.star_rating and api_stars: vals['star_rating'] = api_stars
                    if not hotel.image_url and api_imgs: vals['image_url'] = api_imgs[0]
                    # نحدث الوصف فقط إذا كان المحلي فارغاً
                    if not hotel.description and api_desc: vals['description'] = api_desc
                    
                    if vals:
                        hotel.sudo().with_context(lang=request.env.context.get('lang')).write(vals)

        except Exception as e:
            _logger.warning(f"Static Data Error: {e}")

        # 5. جلب الأسعار (Rates)
        grouped_rooms = {}
        error_msg = ""
        try:
            payload = {
                "hotelIds": [hotel_lite_id],
                "occupancies": [{"adults": int(search_params.get('guests', 2))}],
                "checkin": search_params.get('checkin'),
                "checkout": search_params.get('checkout'),
                "currency": "SAR",
                "guestNationality": "SA",
                "roomMapping": True,
                "language": user_lang
            }
            resp = client.make_request('/hotels/rates', method='POST', json=payload)
            data = resp.get('data', [])
            
            if data:
                for room in data[0].get('roomTypes', []):
                    key = room.get('mappedRoomId') or room.get('roomTypeId')
                    # دمج وصف الغرفة (API Room Desc + Rate Desc)
                    r_desc = room.get('description') or room.get('roomDescription') or ""
                    
                    if key not in grouped_rooms:
                        r_img = None
                        if room.get('photos'): r_img = room['photos'][0].get('url')

                        grouped_rooms[key] = {
                            'name': room.get('name'),
                            'image': r_img or hotel_info['images'][0],
                            'rates': []
                        }
                    
                    for rate in room.get('rates', []):
                        price = rate.get('retailPrice', {}).get('amount') or rate.get('retailRate', {}).get('total', [{}])[0].get('amount')
                        if price:
                            offer_id = rate.get('offerId') or rate.get('rateId')
                            
                            if not grouped_rooms[key]['name']:
                                grouped_rooms[key]['name'] = rate.get('name') or "Standard Room"

                            grouped_rooms[key]['rates'].append({
                                'offer_id': offer_id,
                                'price': price,
                                'name': rate.get('name'),
                                'refundable': rate.get('cancellationPolicies', {}).get('refundableTag') == 'REF',
                                'cancellation_deadline': rate.get('cancellationPolicies', {}).get('cancellationDeadline'),
                                'board': 'Room Only', 
                                'description': r_desc # تمرير وصف الغرفة
                            })
            else:
                error_msg = "No rates available."
        except Exception as e:
            _logger.error(f"Rates Error: {e}")
            error_msg = "Could not load rates."

        return request.render("liteapi_booking.hotel_details_template", {
            'hotel_lite_id': hotel_lite_id,
            'hotel_info': hotel_info,
            'grouped_rooms': grouped_rooms,
            'search_params': search_params,
            'error_msg': error_msg
        })

    # === الكنترولر الجديد: عرض صفحة تفاصيل الغرفة ===
    @http.route(['/booking/room/details'], type='http', auth="public", website=True, methods=['POST'], csrf=False)
    def room_details_page(self, **post):
        """
        عرض صفحة تفاصيل الغرفة الكاملة قبل الحجز.
        يستقبل البيانات من زر 'اختر الغرفة' ويعرضها في قالب منفصل.
        """
        if not post.get('offer_id'):
            # في حال عدم وجود عرض، نعود للبحث
            return request.redirect('/hotel/search')

        # تجهيز البيانات للعرض في القالب الجديد
        details = {
            # البيانات الأساسية للحجز
            'hotel_lite_id': post.get('hotel_lite_id'),
            'offer_id': post.get('offer_id'),
            'price': post.get('price'),
            
            # تفاصيل العرض والغرفة
            'room_name': post.get('room_name'),
            'rate_name': post.get('rate_name'),
            'room_image': post.get('room_image'),
            'room_description': Markup(post.get('room_description') or ""),
            'is_refundable': post.get('is_refundable'),
            'cancellation_deadline': post.get('cancellation_deadline'),
            
            # سياق البحث (يجب تمريره للحفاظ عليه)
            'checkin': post.get('checkin'),
            'checkout': post.get('checkout'),
            'guests': post.get('guests'),
        }

        # عرض القالب الجديد room_details_template
        return request.render("liteapi_booking.room_details_template", {'details': details})