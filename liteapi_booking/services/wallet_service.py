from odoo import models, api, fields, _
from odoo.exceptions import UserError

class WalletService(models.AbstractModel):
    _name = 'liteapi.wallet.service'
    _description = 'Wallet Logic'

    @api.model
    def get_create_wallet(self, partner_id):
        """Get or create wallet for partner"""
        wallet = self.env['customer.wallet'].sudo().search([('partner_id', '=', partner_id)], limit=1)
        if not wallet:
            wallet = self.env['customer.wallet'].sudo().create({'partner_id': partner_id})
        return wallet

    @api.model
    def add_balance(self, partner_id, amount, reference, order_id=False):
        """Top-up Balance"""
        wallet = self.get_create_wallet(partner_id)
        self.env['wallet.transaction'].sudo().create({
            'wallet_id': wallet.id,
            'type': 'topup',
            'amount': abs(amount),
            'reference': reference,
            'sale_order_id': order_id
        })
        return True

    @api.model
    def deduct_balance(self, partner_id, amount, reference, order_id=False):
        """Pay from Wallet"""
        wallet = self.get_create_wallet(partner_id)
        if wallet.balance < abs(amount):
             raise UserError(_("Insufficient Wallet Balance"))
        
        self.env['wallet.transaction'].sudo().create({
            'wallet_id': wallet.id,
            'type': 'booking',
            'amount': -abs(amount),
            'reference': reference,
            'sale_order_id': order_id
        })
        return True
