from odoo import models, fields, api, _
from odoo.exceptions import UserError

class CustomerWallet(models.Model):
    _name = 'customer.wallet'
    _description = 'Customer Wallet'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one('res.partner', string='Customer', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    balance = fields.Monetary(string='Current Balance', compute='_compute_balance', store=True)
    transaction_ids = fields.One2many('wallet.transaction', 'wallet_id', string='Transactions')

    _sql_constraints = [
        ('partner_uniq', 'unique(partner_id)', 'Customer can have only one wallet!'),
    ]

    @api.depends('transaction_ids.amount')
    def _compute_balance(self):
        for wallet in self:
            wallet.balance = sum(wallet.transaction_ids.mapped('amount'))

class WalletTransaction(models.Model):
    _name = 'wallet.transaction'
    _description = 'Wallet Transaction'
    _order = 'date desc, id desc'

    wallet_id = fields.Many2one('customer.wallet', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='wallet_id.currency_id')
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    type = fields.Selection([
        ('topup', 'Top-up'),
        ('booking', 'Booking Payment'),
        ('refund', 'Refund')
    ], required=True)
    amount = fields.Monetary(required=True, help="Positive for Top-up/Refund, Negative for Booking")
    reference = fields.Char(required=True)
    sale_order_id = fields.Many2one('sale.order', string='Related Order')
