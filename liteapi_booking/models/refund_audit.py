from odoo import models, fields, api

class LiteAPIRefundAudit(models.Model):
    _name = 'liteapi.refund.audit'
    _description = 'Refund Audit Log'
    _order = 'create_date desc'

    booking_id = fields.Many2one('liteapi.booking', string='Booking', required=True)
    amount = fields.Monetary(string='Refund Amount', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='booking_id.sale_order_id.currency_id')
    reason = fields.Text(string='Reason', required=True)
    user_id = fields.Many2one('res.users', string='Approved By', default=lambda self: self.env.user)
    date = fields.Datetime(default=fields.Datetime.now)
