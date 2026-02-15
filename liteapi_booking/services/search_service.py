import json
import logging
from datetime import datetime, timedelta
from odoo import models, api, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SearchService(models.AbstractModel):
    _name = 'liteapi.search.service'
    _description = 'LiteAPI Search Handler'

    @api.model
    def search_hotels(self, search_type, search_value, checkin, checkout, guests):
        user_lang = self.env.context.get('lang', 'en_US')[:2]
        cache_key = f"{search_type}|{search_value}|{checkin}|{checkout}|{guests}|{user_lang}"
        
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return json.loads(cached_result)

        return self._fetch_from_api_and_cache(search_type, search_value, checkin, checkout, guests, cache_key)

    @api.model
    def _get_from_cache(self, cache_key):
        cache_entry = self.env['liteapi.search.cache'].search([
            ('cache_key', '=', cache_key),
            ('expires_at', '>', fields.Datetime.now())
        ], limit=1)
        return cache_entry.response_json if cache_entry else False

    @api.model
    def _fetch_from_api_and_cache(self, search_type, search_value, checkin, checkout, guests, cache_key):
        client = self.env['liteapi.client']
        
        payload = {
            "occupancies": [{"adults": int(guests)}],
            "checkin": str(checkin),
            "checkout": str(checkout),
            "currency": "SAR",
            "guestNationality": "SA",
            "roomMapping": True
        }

        if search_type == 'vibe':
            payload['aiSearch'] = search_value
        elif search_type == 'place':
            payload['aiSearch'] = search_value
        else:
            # City Logic
            if not search_value:
                 return {'hotels': [], 'search_id': cache_key}
            
            # Simple check if search_value is city ID
            if str(search_value).isdigit():
                city = self.env['liteapi.city'].browse(int(search_value))
                if not city.exists():
                     return {'hotels': [], 'search_id': cache_key}
                
                local_hotels = self.env['liteapi.hotel'].search([('city_id', '=', city.id)])
                hotel_ids = [str(h.liteapi_hotel_id) for h in local_hotels if h.liteapi_hotel_id]
                
                if not hotel_ids:
                     return {'hotels': [], 'search_id': cache_key}
                payload['hotelIds'] = hotel_ids[:100]
            else:
                # Fallback to AI Search if city is text
                payload['aiSearch'] = str(search_value)

        try:
            response_data = client.make_request('/hotels/rates', method='POST', json=payload)
            hotels_list = []
            api_data = response_data.get('data', [])
            
            if not api_data: 
                return {'hotels': [], 'search_id': cache_key}

            for item in api_data:
                hotel_lite_id = item.get('hotelId')
                if not hotel_lite_id:
                    continue

                lowest_price = 0.0
                rates = item.get('rates', []) or []
                
                # Check for roomTypes rates if main rates empty
                if not rates and item.get('roomTypes'):
                     for rt in item.get('roomTypes'):
                         rates.extend(rt.get('rates', []))
                
                if rates:
                    prices = []
                    for r in rates:
                        amt = r.get('retailPrice', {}).get('amount') or r.get('retailRate', {}).get('total', [{}])[0].get('amount')
                        if amt: prices.append(amt)
                    if prices:
                        lowest_price = min(prices)

                if lowest_price > 0:
                    local_hotel = self.env['liteapi.hotel'].search([('liteapi_hotel_id', '=', hotel_lite_id)], limit=1)
                    
                    image_url = '/web/static/src/img/placeholder.png'
                    if local_hotel and local_hotel.image_url:
                        image_url = local_hotel.image_url
                    elif item.get('hotelImages'):
                        image_url = item['hotelImages'][0].get('url')

                    hotels_list.append({
                        'id': local_hotel.id if local_hotel else 0,
                        'liteapi_id': hotel_lite_id,
                        'name': item.get('name') or (local_hotel.name if local_hotel else "Unknown Hotel"),
                        'price': lowest_price,
                        'currency': 'SAR',
                        'star_rating': int(item.get('starRating', 0)),
                        'image_url': image_url,
                        'address': item.get('address'),
                        'review_score': item.get('reviewScore', 0),
                        'taxes_included': True
                    })

            final_result = {'hotels': hotels_list, 'search_id': cache_key}
            
            # Cache logic (Simplified)
            try:
                self.env['liteapi.search.cache'].create({
                    'cache_key': cache_key,
                    'city_id': int(search_value) if str(search_value).isdigit() else False,
                    'checkin_date': checkin,
                    'checkout_date': checkout,
                    'guests': guests,
                    'response_json': json.dumps(final_result),
                    'expires_at': fields.Datetime.now() + timedelta(minutes=15)
                })
            except:
                pass # Ignore cache errors
            
            return final_result

        except Exception as e:
             _logger.error(f"Search Service Error: {e}")
             # Return empty to avoid 500 error in controller
             return {'hotels': [], 'search_id': cache_key}