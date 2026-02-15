from odoo import models, fields, api
from datetime import timedelta # <--- يجب إضافة هذا السطر

class LiteAPIAudit(models.Model):
    _name = 'liteapi.audit.log'
    _description = 'LiteAPI Audit Log'
    _order = 'create_date desc'

    name = fields.Char(string='Endpoint', required=True)
    timestamp = fields.Datetime(default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', string='User')
    result = fields.Selection([
        ('success', 'Success'),
        ('blocked', 'Blocked'),
        ('error', 'Error')
    ], string='Result', required=True)
    details = fields.Text(string='Details')

    @api.model
    def _gc_old_logs(self):
        """Delete logs older than 30 days"""
        # التصحيح هنا: استخدام timedelta مباشرة
        limit_date = fields.Datetime.now() - timedelta(days=30)
        self.search([('create_date', '<', limit_date)]).unlink()