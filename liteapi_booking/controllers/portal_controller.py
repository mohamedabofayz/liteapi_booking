from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

class LiteAPIPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        if 'booking_count' in counters:
            values['booking_count'] = request.env['liteapi.booking'].search_count([('partner_id', '=', partner.id)])
        return values

    @http.route(['/my/dashboard'], type='http', auth="user", website=True)
    def portal_my_dashboard_custom(self, **kw):
        partner = request.env.user.partner_id
        wallet = request.env['liteapi.wallet.service'].sudo().get_create_wallet(partner.id)
        
        bookings = request.env['liteapi.booking'].search([
            ('partner_id', '=', partner.id)
        ], order='create_date desc', limit=5)

        values = {
            'wallet': wallet,
            'bookings': bookings,
            'page_name': 'dashboard',
        }
        return request.render("liteapi_booking.portal_my_dashboard", values)

    @http.route(['/my/bookings', '/my/bookings/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_bookings(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Booking = request.env['liteapi.booking']
        domain = [('partner_id', '=', partner.id)]
        booking_count = Booking.search_count(domain)
        pager = portal_pager(
            url="/my/bookings",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=booking_count,
            page=page,
            step=10
        )
        bookings = Booking.search(domain, order='create_date desc', limit=10, offset=pager['offset'])
        values.update({
            'bookings': bookings,
            'page_name': 'booking',
            'pager': pager,
            'default_url': '/my/bookings',
        })
        return request.render("liteapi_booking.portal_my_bookings", values)

    @http.route(['/my/bookings/<int:booking_id>'], type='http', auth="user", website=True)
    def portal_my_booking_detail(self, booking_id, **kw):
        booking = request.env['liteapi.booking'].browse(booking_id)
        if not booking.exists() or booking.partner_id != request.env.user.partner_id:
             return request.redirect('/my/bookings')
        return request.render("liteapi_booking.portal_booking_detail", {
            'booking': booking,
            'page_name': 'booking',
        })

    @http.route(['/my/wallet'], type='http', auth="user", website=True)
    def portal_my_wallet(self, **kw):
        partner = request.env.user.partner_id
        wallet = request.env['liteapi.wallet.service'].sudo().get_create_wallet(partner.id)
        values = {
            'wallet': wallet,
            'transactions': wallet.transaction_ids,
            'page_name': 'wallet',
        }
        return request.render("liteapi_booking.portal_my_wallet", values)