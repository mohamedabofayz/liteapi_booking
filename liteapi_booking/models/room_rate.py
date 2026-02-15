from odoo import models, fields, api

class LiteAPIRoomRate(models.Model):
    _name = 'liteapi.room.rate'
    _description = 'LiteAPI Room Rate (Temporary)'
    _order = 'create_date desc'

    hotel_id = fields.Many2one('liteapi.hotel', required=True)
    room_type = fields.Char(required=True)
    rate_key = fields.Char(required=True, help="Key from LiteAPI /rates")
    price = fields.Float(required=True)
    currency = fields.Char(required=True, default='SAR')
    is_refundable = fields.Boolean(default=False)
    expires_at = fields.Datetime(required=True)

    @api.model
    def _clean_expired_rates(self):
        """Cron job to delete expired rate entries"""
        self.search([('expires_at', '<', fields.Datetime.now())]).unlink()
