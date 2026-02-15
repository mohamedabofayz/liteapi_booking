from odoo import models, fields

class LiteAPICountry(models.Model):
    _name = 'liteapi.country'
    _description = 'LiteAPI Country'

    name = fields.Char(required=True)
    code = fields.Char(required=True, default='SA')
