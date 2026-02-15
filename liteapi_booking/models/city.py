from odoo import models, fields

class LiteAPICity(models.Model):
    _name = 'liteapi.city'
    _description = 'LiteAPI City'

    name = fields.Char(required=True)
    liteapi_city_id = fields.Char(string='LiteAPI City ID', required=True)
    country_id = fields.Many2one('liteapi.country', string='Country', required=True)
    is_active = fields.Boolean(string='Active', default=False)
