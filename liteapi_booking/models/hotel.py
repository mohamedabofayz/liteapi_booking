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
    
    # --- الحقول الذكية ---
    image_url = fields.Char(string='Cached Image URL')
    star_rating = fields.Integer(string='Cached Star Rating', default=0)
    
    # هذه هي النقطة الجوهرية: translate=True
    # تعني أن Odoo سيحفظ قيمة مستقلة لكل لغة (AR, EN)
    description = fields.Html(string='Cached Description', translate=True)
    
    amenities = fields.Text(string='Cached Amenities')