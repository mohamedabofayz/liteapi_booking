from odoo import models, fields

class LiteAPIHotel(models.Model):
    _name = 'liteapi.hotel'
    _description = 'LiteAPI Hotel'

    name = fields.Char(required=True)
    liteapi_hotel_id = fields.Char(string='LiteAPI Hotel ID', required=True)
    city_id = fields.Many2one('liteapi.city', string='City', required=True)
    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))
    is_cached = fields.Boolean(string='Cached', default=False)
    
    # الحقل الجديد لتخزين الصورة المصغرة
    image_url = fields.Char(string='Image URL')