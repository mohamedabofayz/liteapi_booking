from odoo import models, fields, api

class LiteAPIAdminDashboard(models.TransientModel):
    _name = 'liteapi.admin.dashboard'
    _description = 'LiteAPI Admin Dashboard'

    name = fields.Char(default="Admin Dashboard")
    
    # KPIs
    today_searches = fields.Integer(compute='_compute_kpis')
    today_bookings = fields.Integer(compute='_compute_kpis')
    today_errors = fields.Integer(compute='_compute_kpis')
    wallet_liability = fields.Float(compute='_compute_kpis', string="Total Wallet Liability")
    cache_hit_ratio = fields.Float(compute='_compute_kpis', string="Cache Hit Ratio %")

    @api.depends('name')
    def _compute_kpis(self):
        for rec in self:
            today = fields.Date.today()
            # Searches (Count of cache checks or api calls in search service?)
            # Approximation via Log
            rec.today_searches = self.env['liteapi.audit.log'].search_count([
                ('create_date', '>=', today), 
                ('name', 'ilike', 'Search:')
            ])
            
            # Bookings
            rec.today_bookings = self.env['liteapi.booking'].search_count([
                ('create_date', '>=', today), 
                ('status', '=', 'confirmed')
            ])

            # Errors
            rec.today_errors = self.env['liteapi.audit.log'].search_count([
                ('create_date', '>=', today), 
                ('result', 'in', ['blocked', 'error'])
            ])

            # Wallet Liability (Total Balances)
            rec.wallet_liability = sum(self.env['customer.wallet'].search([]).mapped('balance'))

            # Cache Hit Ratio (Last 24h)
            logs = self.env['liteapi.audit.log'].search([
                ('create_date', '>=', today), 
                ('name', 'ilike', 'Search:')
            ])
            hits = len(logs.filtered(lambda l: 'Cache Hit' in (l.details or '')))
            total = len(logs)
            rec.cache_hit_ratio = (hits / total * 100) if total > 0 else 0.0
