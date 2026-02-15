from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class LiteAPIBookingController(http.Controller):

    @http.route('/liteapi/confirm-booking', type='http', auth='user', methods=['POST'], csrf=False)
    def confirm_booking(self, **post):
        order_id = post.get('order_id')
        if not order_id:
             return "Missing Order ID"
        
        try:
            service = request.env['liteapi.booking.service'].sudo()
            booking = service.confirm_booking_from_order(int(order_id))
            
            if booking:
                 return f"Booking Confirmed: {booking.liteapi_booking_id}"
            else:
                 return "Booking Skipped (Duplicate or Error)"

        except Exception as e:
            _logger.exception("Booking Controller Error")
            return f"Booking Failed: {str(e)}"