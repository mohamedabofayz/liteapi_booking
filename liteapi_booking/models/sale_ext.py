from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ==========================================================================
    # حقول جديدة لدعم LiteAPI Payment SDK
    # ==========================================================================
    # يتم تعبئة هذه الحقول بعد استدعاء endpoint الـ prebook وقبل عرض صفحة الدفع
    # --------------------------------------------------------------------------
    liteapi_prebook_id = fields.Char(
        string="LiteAPI Prebook ID", 
        copy=False, 
        help="المعرف المطلوب لتثبيت الحجز في الخطوة النهائية"
    )
    liteapi_transaction_id = fields.Char(
        string="LiteAPI Transaction ID", 
        copy=False, 
        help="معرف المعاملة المستخدم في SDK وفي تثبيت الحجز"
    )
    liteapi_secret_key = fields.Char(
        string="LiteAPI Secret Key", 
        copy=False, 
        help="المفتاح السري لتشغيل نافذة الدفع في الواجهة الأمامية"
    )

    def action_confirm(self):
        """
        Override to trigger booking when order is confirmed.
        In Odoo, confirmation usually equals 'sale' state if no payment flow issues.
        """
        res = super(SaleOrder, self).action_confirm()
        
        for order in self:
            # Check if this order contains LiteAPI items (simple check for now)
            # In real impl, we'd check line products or flags
            # Here we assume if it's confirmed and paid, we try booking
            
            # TRIGGER BOOKING
            try:
                # 1. Booking Trigger (if it's a booking order)
                # We assume booking service checks internally if it's a booking order or just a topup
                self.env['liteapi.booking.service'].sudo().confirm_booking_from_order(order.id)
                
                # 2. Wallet Top-up Trigger
                # Check for Top-up products
                for line in order.order_line:
                    if line.product_id.default_code == 'WALLET_TOPUP':
                        self.env['liteapi.wallet.service'].sudo().add_balance(
                            order.partner_id.id, 
                            line.price_subtotal, 
                            order.name, 
                            order.id
                        )
            except Exception as e:
                # We log but DO NOT RAISE to allow the Order to be confirmed locally.
                # Ops team needs to monitor 'liteapi.booking' for 'failed' status.
                pass
        
        return res

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # LiteAPI Metadata to store what exactly is being booked
    liteapi_hotel_id = fields.Many2one('liteapi.hotel', string='Hotel')
    liteapi_rate_key = fields.Char(string='Rate Key')
    checkin_date = fields.Date(string='Check-in')
    checkout_date = fields.Date(string='Check-out')
    guests = fields.Integer(string='Guests', default=1)
    room_type_name = fields.Char(string='Room Type') # e.g. "Superior King"