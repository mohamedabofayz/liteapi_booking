from odoo import models, fields, api

class LiteAPISearchCache(models.Model):
    _name = 'liteapi.search.cache'
    _description = 'LiteAPI Search Cache'
    _order = 'create_date desc'

    cache_key = fields.Char(required=True, index=True, help="Format: city_id|checkin|checkout|guests")
    # تم تغيير required إلى False لدعم بحث Vibe
    city_id = fields.Many2one('liteapi.city', required=False) 
    checkin_date = fields.Date(required=True)
    checkout_date = fields.Date(required=True)
    guests = fields.Integer(required=True)
    response_json = fields.Text(required=True)
    expires_at = fields.Datetime(required=True)

    _sql_constraints = [
        ('cache_key_unique', 'unique(cache_key)', 'Cache key must be unique!')
    ]

    @api.model
    def _clean_expired_cache(self):
        """Cron job to delete expired cache entries"""
        self.search([('expires_at', '<', fields.Datetime.now())]).unlink()