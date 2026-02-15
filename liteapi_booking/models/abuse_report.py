from odoo import models, fields, api, tools

class LiteAPIAbuseReport(models.Model):
    _name = "liteapi.abuse.report"
    _description = "Abuse Analysis Report"
    _auto = False # SQL View

    user_id = fields.Many2one('res.users', string='User', readonly=True)
    search_count = fields.Integer(string='Searches', readonly=True)
    booking_count = fields.Integer(string='Bookings', readonly=True)
    ratio = fields.Float(string='Book/Search Ratio', readonly=True)
    risk_level = fields.Selection([('low', 'Low'), ('high', 'High Risk')], string='Risk', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    row_number() OVER () as id,
                    u.id as user_id,
                    count(l.id) as search_count,
                    count(b.id) as booking_count,
                    CASE 
                        WHEN count(l.id) = 0 THEN 0 
                        ELSE CAST(count(b.id) AS FLOAT) / CAST(count(l.id) AS FLOAT) 
                    END as ratio,
                    CASE 
                        WHEN count(l.id) > 20 AND count(b.id) = 0 THEN 'high'
                        ELSE 'low'
                    END as risk_level
                FROM res_users u
                LEFT JOIN liteapi_audit_log l ON l.user_id = u.id AND l.name LIKE 'Search%%'
                LEFT JOIN liteapi_booking b ON b.sale_order_id IN (SELECT id FROM sale_order WHERE user_id = u.id)
                GROUP BY u.id
                HAVING count(l.id) > 0
            )
        """ % (self._table,))
