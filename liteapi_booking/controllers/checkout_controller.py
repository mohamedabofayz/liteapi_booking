from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class LiteAPICheckoutController(http.Controller):

    @http.route(['/hotel/prebook'], type='http', auth="public", website=True, methods=['POST'], csrf=False)
    def hotel_prebook(self, **post):
        """
        يستقبل offer_id من العميل، وينفذ Prebook للحصول على مفاتيح الدفع.
        """
        # 1. استقبال البيانات من النموذج
        offer_id = post.get('offer_id')
        hotel_lite_id = post.get('hotel_lite_id')
        price = post.get('price')
        checkin = post.get('checkin')
        checkout = post.get('checkout')
        guests = int(post.get('guests', 2))

        # سياق البحث (ضروري لإعادة المحاولة في الـ Service في حال فشل العرض)
        search_context = {
            'hotel_lite_id': hotel_lite_id,
            'checkin': checkin,
            'checkout': checkout,
            'guests': guests,
            'price': price
        }
        
        try:
            _logger.info(f"🚀 Prebook Controller: Processing Offer {offer_id} for Hotel {hotel_lite_id}")
            
            service = request.env['liteapi.booking.service'].sudo()
            
            # تنفيذ عملية Prebook والحصول على مفاتيح الدفع
            prebook_data = service.execute_prebook_api(
                offer_id, 
                search_context=search_context
            )
            
            # [Smart Update] تحديث السعر والعرض إذا تغير أثناء الـ Retry في السيرفس
            final_offer_id = prebook_data.get('offerId') or offer_id
            final_price = prebook_data.get('price') or price
            currency = prebook_data.get('currency', 'SAR')
            
            if prebook_data.get('is_refreshed'):
                _logger.info(f"ℹ️ Booking Offer Updated: {price} -> {final_price}")

            # 2. حفظ بيانات الحجز والدفع في الجلسة
            # هذه البيانات ستستخدمها صفحة الدفع (Checkout) لتهيئة الـ SDK
            request.session['liteapi_booking_session'] = {
                # مفاتيح الدفع الحساسة
                'prebook_id': prebook_data.get('prebookId'),
                'transaction_id': prebook_data.get('transactionId'),
                'secret_key': prebook_data.get('secretKey'), 
                
                # تفاصيل الحجز
                'hotel_lite_id': hotel_lite_id,
                'offer_id': final_offer_id,
                'price': final_price,
                'currency': currency,
                'checkin': checkin,
                'checkout': checkout,
                'guests': guests
            }
            
            # التوجيه إلى صفحة الدفع
            return request.redirect('/hotel/checkout')

        except Exception as e:
            _logger.error(f"Prebook Controller Error: {e}")
            # في حال الخطأ، نعود لصفحة الفندق مع رسالة خطأ
            error_msg = str(e).replace("'", "").replace('"', "")
            return request.redirect(f'/booking/view/{hotel_lite_id}?error={error_msg}')

    @http.route(['/hotel/checkout'], type='http', auth="public", website=True)
    def hotel_checkout(self, **kw):
        """
        عرض صفحة الدفع وتهيئة الـ SDK.
        """
        session = request.session.get('liteapi_booking_session')
        if not session: 
            # إذا لم تكن هناك جلسة نشطة، نعود للبحث
            return request.redirect('/hotel/search')
        
        # تحديد البيئة (Sandbox/Live) لضبط المفتاح العام في القالب
        api_key = request.env['ir.config_parameter'].sudo().get_param('liteapi.api_key')
        # تخمين بسيط: إذا كان المفتاح يحتوي على 'sand'، نعتبره Sandbox
        is_sandbox = 'sandbox' in (api_key or '').lower() or 'sand_' in (api_key or '').lower()
        
        return request.render("liteapi_booking.checkout_page", {
            'session_data': session,
            # تمرير المفتاح العام للقالب (يستخدم لتهيئة SDK)
            'public_key': 'sandbox' if is_sandbox else 'live',
            'return_url': '/booking/confirm'
        })

    @http.route(['/booking/confirm'], type='http', auth="public", website=True, csrf=False)
    def booking_confirm(self, **kw):
        """
        يتم استدعاء هذا الرابط بعد نجاح عملية الدفع في الـ SDK.
        يقوم بالتثبيت النهائي للحجز (Book Request).
        """
        session = request.session.get('liteapi_booking_session')
        if not session: 
            return request.redirect('/')

        try:
            # جلب بيانات النزيل المحفوظة مؤقتاً
            guest = request.session.get('liteapi_guest_info', {
                'first_name': 'Guest', 
                'last_name': 'User', 
                'email': 'guest@example.com'
            })
            
            # التثبيت النهائي للحجز عبر السيرفس
            booking_response = request.env['liteapi.booking.service'].sudo().finalize_booking_api(
                session['prebook_id'], 
                session['transaction_id'], 
                guest,
                booking_meta=session 
            )
            
            # تنظيف الجلسة بعد النجاح
            request.session.pop('liteapi_booking_session', None)
            
            # عرض صفحة التأكيد
            # ملاحظة: booking_response يحتوي على بيانات الحجز من API
            # ولكن القالب قد يتوقع كائن Booking من أودو. 
            # سنقوم بجلب أحدث حجز تم إنشاؤه لهذا الإيميل للعرض (أو تمرير البيانات مباشرة)
            
            # الخيار الأفضل: البحث عن الحجز الذي تم إنشاؤه للتو باستخدام bookingId
            liteapi_booking_id = booking_response.get('bookingId')
            booking_record = request.env['liteapi.booking'].sudo().search([('liteapi_booking_id', '=', liteapi_booking_id)], limit=1)
            
            return request.render("liteapi_booking.confirmation_page", {'booking': booking_record})

        except Exception as e:
            _logger.error(f"Confirmation Error: {e}")
            return f"Booking Error: {str(e)}"

    @http.route(['/hotel/save_guest'], type='json', auth="public", website=True)
    def save_guest_info(self, **kw):
        """
        حفظ بيانات النزيل في الجلسة بشكل مؤقت أثناء الكتابة في نموذج الدفع.
        """
        request.session['liteapi_guest_info'] = kw
        return True