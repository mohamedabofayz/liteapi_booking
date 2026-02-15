from odoo import models, fields, api, _

class LiteAPIBooking(models.Model):
    _name = 'liteapi.booking'
    _description = 'LiteAPI Hotel Booking'
    _order = 'create_date desc'

    # الحقول الأساسية
    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    
    # العلاقات
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')
    hotel_id = fields.Many2one('liteapi.hotel', string='Hotel')

    # تفاصيل الحجز
    liteapi_booking_id = fields.Char(string='LiteAPI Booking ID', help="Booking ID from LiteAPI system")
    prebook_id = fields.Char(string='Prebook ID')
    transaction_id = fields.Char(string='Transaction ID')
    
    hotel_name = fields.Char(string='Hotel Name')
    room_type = fields.Char(string='Room Type')
    
    checkin_date = fields.Date(string='Check-in')
    checkout_date = fields.Date(string='Check-out')
    guests = fields.Integer(string='Guests', default=1)
    
    guest_name = fields.Char(string='Guest Name')
    email = fields.Char(string='Email')
    
    price = fields.Float(string='Total Price')
    currency = fields.Char(string='Currency', default='SAR')
    
    status = fields.Selection([
        ('draft', 'Pending Payment'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], default='draft', string='Status')

    booking_details = fields.Text(string='Full Response JSON')

    # --- حقول سياسة الإلغاء ---
    is_refundable = fields.Boolean(string="Refundable")
    cancellation_deadline = fields.Datetime(string="Cancellation Deadline")
    cancellation_policy = fields.Text(string="Cancellation Policy")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('liteapi.booking') or 'New'
        return super(LiteAPIBooking, self).create(vals)

    # -------------------------------------------------------------------------
    # Actions (Fix for the error)
    # -------------------------------------------------------------------------
    def action_cancel_and_refund_wizard(self):
        """Opens the refund wizard passing the current booking context"""
        self.ensure_one()
        return {
            'name': _('Cancel & Refund'),
            'type': 'ir.actions.act_window',
            'res_model': 'liteapi.refund.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_booking_id': self.id},
        }