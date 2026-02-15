from odoo import http
from odoo.http import request
import logging
import json

try:
    from odoo.tools import Markup
except ImportError:
    try:
        from markupsafe import Markup
    except ImportError:
        def Markup(text): return text

_logger = logging.getLogger(__name__)

class LiteAPIController(http.Controller):

    # --- Debug ---
    @http.route('/hotel/debug', type='http', auth='public', website=True)
    def list_all_hotels_debug(self):
        hotels = request.env['liteapi.hotel'].sudo().search([])
        if not hotels:
            return "<h1>❌ لا توجد فنادق!</h1>"
        html = "<ul>"
        for h in hotels:
            link = f"/booking/view/{h.liteapi_hotel_id}"
            html += f"<li>{h.name} -> <a href='{link}'>عرض</a></li>"
        html += "</ul>"
        return html

    # --- Search ---
    @http.route(['/hotel/search'], type='http', auth="public", website=True)
    def hotel_search_page(self, **kwargs):
        cities = request.env['liteapi.city'].sudo().search([('is_active', '=', True)])
        return request.render("liteapi_booking.hotel_search_template", {'cities': cities})

    # --- Results ---
    @http.route(['/hotel/results'], type='http', auth="public", website=True, methods=['POST', 'GET'], csrf=False)
    def hotel_search_results(self, **kwargs):
        search_type = kwargs.get('search_type', 'city')
        # Fix: handle potential NoneType for search values
        search_value = kwargs.get('search_query') or kwargs.get('search_query_vibe') if search_type == 'vibe' else kwargs.get('city_id')
        
        checkin = kwargs.get('checkin')
        checkout = kwargs.get('checkout')
        guests = kwargs.get('guests', 2)

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

        return request.render("liteapi_booking.hotel_search_results_template", {
            'hotels': hotels,
            'guests': guests,
            'search_type': search_type
        })

    # --- Details ---
    @http.route(['/booking/view/<string:hotel_lite_id>'], type='http', auth="public", website=True)
    def hotel_details(self, hotel_lite_id, **kwargs):
        hotel = request.env['liteapi.hotel'].sudo().search([('liteapi_hotel_id', '=', hotel_lite_id)], limit=1)
        search_params = request.session.get('liteapi_search')
        if not search_params:
             return request.redirect('/hotel/search')

        client = request.env['liteapi.client'].sudo()
        
        # Default Data to prevent KeyErrors
        hotel_info = {
            'name': hotel.name if hotel else "Hotel Details",
            'address': getattr(hotel, 'name', '') or "", # Fallback
            'rating': 0.0, 'review_count': 0, 'stars': 0,
            'images': ['/web/static/src/img/placeholder.png'],
            'description': "", 'facilities': [], 'google_maps_link': "#"
        }

        # 1. Static Data
        try:
            d_resp = client.make_request('/data/hotel', method='GET', params={'hotelId': hotel_lite_id})
            d_data = d_resp.get('data', {})
            if d_data:
                hotel_info.update({
                    'name': d_data.get('name') or hotel_info['name'],
                    'address': d_data.get('address') or hotel_info['address'],
                    'rating': d_data.get('rating', 0.0),
                    'stars': int(d_data.get('starRating', 0)),
                    'description': Markup(d_data.get('description') or ""),
                    'facilities': d_data.get('hotelFacilities', [])
                })
                imgs = [i['url'] for i in d_data.get('hotelImages', []) if i.get('url')]
                if imgs: hotel_info['images'] = imgs
        except Exception as e:
            _logger.warning(f"Static Data Error: {e}")

        # 2. Rates
        grouped_rooms = {}
        error_msg = ""
        try:
            payload = {
                "hotelIds": [hotel_lite_id],
                "occupancies": [{"adults": int(search_params.get('guests', 2))}],
                "checkin": search_params['checkin'],
                "checkout": search_params['checkout'],
                "currency": "SAR",
                "guestNationality": "SA",
                "roomMapping": True
            }
            resp = client.make_request('/hotels/rates', method='POST', json=payload)
            data = resp.get('data', [])
            
            if data:
                for room in data[0].get('roomTypes', []):
                    key = room.get('mappedRoomId') or room.get('roomTypeId')
                    # Room Name Logic
                    r_name = room.get('name')
                    
                    if key not in grouped_rooms:
                        # Try getting image from room photos
                        r_img = None
                        if room.get('photos'):
                             r_img = room['photos'][0].get('url')

                        grouped_rooms[key] = {
                            'name': r_name, # Can be null initially
                            'image': r_img or hotel_info['images'][0],
                            'rates': []
                        }
                    
                    for rate in room.get('rates', []):
                        price = rate.get('retailPrice', {}).get('amount') or rate.get('retailRate', {}).get('total', [{}])[0].get('amount')
                        if price:
                            offer_id = rate.get('offerId') or rate.get('rateId')
                            
                            # Fallback Name if room type has no name
                            if not grouped_rooms[key]['name']:
                                grouped_rooms[key]['name'] = rate.get('name') or "Standard Room"

                            grouped_rooms[key]['rates'].append({
                                'offer_id': offer_id,
                                'price': price,
                                'name': rate.get('name'),
                                'refundable': rate.get('cancellationPolicies', {}).get('refundableTag') == 'REF',
                                # --- FIX: Add cancellation_deadline safely ---
                                'cancellation_deadline': rate.get('cancellationPolicies', {}).get('cancellationDeadline'),
                                'board': 'Room Only'
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

    # --- Prebook ---
    @http.route(['/hotel/prebook'], type='http', auth="public", website=True, methods=['POST'], csrf=False)
    def hotel_prebook(self, **post):
        offer_id = post.get('offer_id')
        hotel_lite_id = post.get('hotel_lite_id')
        
        try:
            prebook_data = request.env['liteapi.booking.service'].sudo().execute_prebook_api(offer_id)
            
            request.session['liteapi_booking_session'] = {
                'prebook_id': prebook_data['prebookId'],
                'transaction_id': prebook_data['transactionId'],
                'secret_key': prebook_data['secretKey'], 
                'hotel_lite_id': hotel_lite_id,
                'offer_id': offer_id,
                'price': post.get('price'),
                'currency': 'SAR'
            }
            return request.redirect('/hotel/checkout')
        except Exception as e:
            return request.redirect(f'/booking/view/{hotel_lite_id}?error={str(e)}')

    # --- Checkout & Confirmation ---
    @http.route(['/hotel/checkout'], type='http', auth="public", website=True)
    def hotel_checkout(self, **kw):
        session = request.session.get('liteapi_booking_session')
        if not session: return request.redirect('/hotel/search')
        
        api_key = request.env['ir.config_parameter'].sudo().get_param('liteapi.api_key')
        return request.render("liteapi_booking.checkout_page", {
            'session_data': session,
            'public_key': 'sandbox' if 'sandbox' in (api_key or '').lower() else 'live',
            'return_url': '/booking/confirm'
        })

    @http.route(['/booking/confirm'], type='http', auth="public", website=True, csrf=False)
    def booking_confirm(self, **kw):
        session = request.session.get('liteapi_booking_session')
        if not session: return request.redirect('/')

        try:
            guest = request.session.get('liteapi_guest_info', {'first_name': 'Guest', 'last_name': 'User', 'email': 'guest@example.com'})
            booking = request.env['liteapi.booking.service'].sudo().finalize_booking_api(
                session['prebook_id'], session['transaction_id'], guest
            )
            request.session.pop('liteapi_booking_session', None)
            return request.render("liteapi_booking.confirmation_page", {'booking': booking})
        except Exception as e:
            return f"Booking Error: {str(e)}"

    @http.route(['/hotel/save_guest'], type='json', auth="public", website=True)
    def save_guest_info(self, **kw):
        request.session['liteapi_guest_info'] = kw
        return True