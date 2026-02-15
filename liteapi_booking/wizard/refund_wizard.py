from odoo import models, fields, api, _
from odoo.exceptions import UserError

class LiteAPIRefundWizard(models.TransientModel):
    _name = 'liteapi.refund.wizard'
    _description = 'Manual Refund to Wallet'

    booking_id = fields.Many2one('liteapi.booking', required=True, readonly=True)
    amount = fields.Float(string='Refund Amount', required=True)
    reason = fields.Text(string='Cancellation Reason', required=True)
    currency_id = fields.Many2one('res.currency', related='booking_id.sale_order_id.currency_id')

    @api.model
    def default_get(self, fields):
        res = super(LiteAPIRefundWizard, self).default_get(fields)
        if self.env.context.get('default_booking_id'):
            booking = self.env['liteapi.booking'].browse(self.env.context['default_booking_id'])
            # Suggest full amount by default
            order_amount = booking.sale_order_id.amount_total
            res['amount'] = order_amount
        return res

    def action_confirm_refund(self):
        self.ensure_one()
        booking = self.booking_id
        
        if booking.status != 'confirmed':
            raise UserError(_("Only confirmed bookings can be cancelled and refunded."))

        # 1. Update Wallet (Credit)
        self.env['liteapi.wallet.service'].sudo().add_balance(
            booking.partner_id.id,
            self.amount,
            f"Refund: {booking.name}",
            booking.sale_order_id.id
        )

        # 2. Log Audit
        self.env['liteapi.refund.audit'].create({
            'booking_id': booking.id,
            'amount': self.amount,
            'reason': self.reason,
            'user_id': self.env.uid
        })

        # 3. Update Booking Status
        booking.write({'status': 'cancelled'})
        
        return {'type': 'ir.actions.act_window_close'}
