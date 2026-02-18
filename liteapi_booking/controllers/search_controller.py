from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class LiteAPISearchController(http.Controller):

    @http.route(['/hotel/search'], type='http', auth="public", website=True)
    def hotel_search_page(self, **kwargs):
        cities = request.env['liteapi.city'].sudo().search([('is_active', '=', True)])
        return request.render("liteapi_booking.hotel_search_template", {'cities': cities})

    @http.route(['/hotel/results'], type='http', auth="public", website=True, methods=['POST', 'GET'], csrf=False)
    def hotel_search_results(self, **kwargs):
        session_search = request.session.get('liteapi_search', {})
        
        # استرجاع المعايير
        search_type = kwargs.get('search_type') or session_search.get('search_type', 'city')
        search_value = kwargs.get('search_query') or kwargs.get('search_query_vibe') or kwargs.get('city_id') or session_search.get('search_value')
        checkin = kwargs.get('checkin') or session_search.get('checkin')
        checkout = kwargs.get('checkout') or session_search.get('checkout')
        guests = kwargs.get('guests') or session_search.get('guests', 2)

        # تحديث الجلسة
        request.session['liteapi_search'] = {
            'search_type': search_type,
            'search_value': search_value,
            'checkin': checkin,
            'checkout': checkout,
            'guests': guests
        }

        hotels = []
        if search_value and checkin and checkout:
            try:
                service = request.env['liteapi.search.service'].sudo()
                result = service.search_hotels(search_type, search_value, checkin, checkout, guests)
                hotels = result.get('hotels', [])
            except Exception as e:
                _logger.error(f"Search Error: {e}")

        # === إصلاح الفلتر ===
        star_filters = request.httprequest.form.getlist('stars') 
        selected_stars = []
        
        if star_filters:
            try:
                # تحويل القيم القادمة من النموذج إلى أرقام صحيحة
                selected_stars = [int(s) for s in star_filters]
                _logger.info(f"🔍 Applying Filters: {selected_stars}")
                
                # الفلترة: التحقق من وجود 'star_rating' وتحويله إلى int للمقارنة
                hotels = [
                    h for h in hotels 
                    if int(h.get('star_rating') or 0) in selected_stars
                ]
            except ValueError:
                pass 
        
        # الترتيب حسب السعر (اختياري لتحسين العرض)
        hotels = sorted(hotels, key=lambda x: x['price'])

        return request.render("liteapi_booking.hotel_search_results_template", {
            'hotels': hotels,
            'guests': guests,
            'search_type': search_type,
            'search_params': request.session['liteapi_search'],
            'selected_stars': selected_stars
        })