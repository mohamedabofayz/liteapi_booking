import logging
import json
import urllib.parse
import http.client
import ssl
from odoo import models, api, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

ALLOWED_ENDPOINTS = [
    '/hotels/rates',
    '/hotels/min-rates',
    '/hotels/details',
    '/rates',
    '/booking',
    '/rates/prebook',
    '/rates/book',
    '/data/cities',
    '/data/hotels',
    '/data/hotel',
    '/data/places'
]

class LiteAPIClient(models.AbstractModel):
    _name = 'liteapi.client'
    _description = 'LiteAPI Client Service'

    @api.model
    def _get_config(self):
        ICP = self.env['ir.config_parameter'].sudo()
        base_url = ICP.get_param('liteapi.base_url')
        api_key = ICP.get_param('liteapi.api_key')
        return base_url, api_key

    @api.model
    def _log_call(self, endpoint, result, details=""):
        """
        تسجيل العمليات في السجل مع دعم النصوص الطويلة.
        """
        try:
            self.env['liteapi.audit.log'].sudo().create({
                'name': endpoint,
                'user_id': self.env.uid,
                'result': result,
                # [MODIFIED] تمت إزالة القيد [:1000] للسماح بتسجيل كامل المحتوى
                'details': details 
            })
        except Exception as e:
            _logger.error(f"Failed to write to audit log: {e}")

    @api.model
    def check_safety(self, endpoint):
        is_allowed = False
        for allowed in ALLOWED_ENDPOINTS:
            if endpoint == allowed or endpoint.startswith(allowed + '?') or endpoint.startswith(allowed + '/'):
                 is_allowed = True
                 break
        if not is_allowed:
            raise AccessError(_("BLOCKED: API Endpoint '%s' is not in the allowlist.") % endpoint)
        return True

    @api.model
    def make_request(self, endpoint, method='GET', custom_base_url=None, **kwargs):
        """
        تنفيذ طلب HTTP مع تسجيل تفصيلي (Full Logging) للإرسال والاستقبال.
        """
        self.check_safety(endpoint)
        base_url, api_key = self._get_config()
        
        if custom_base_url:
            base_url = custom_base_url
        
        if not base_url or not api_key:
            raise UserError("Configuration Error: Missing Base URL or API Key")

        base_url = base_url.strip().rstrip('/')
        api_key = api_key.strip()

        full_url = f"{base_url}{endpoint}"
        
        try:
            parsed = urllib.parse.urlparse(full_url)
            host = parsed.netloc
            path = parsed.path
        except Exception as e:
            raise UserError(f"Invalid URL Format: {full_url}")

        params = kwargs.get('params', {})
        if params:
            query_string = urllib.parse.urlencode(params)
            path = f"{path}?{query_string}"

        body = None
        if method.upper() == 'POST':
            json_payload = kwargs.get('json', {})
            body = json.dumps(json_payload)

        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Language": self.env.context.get('lang', 'en_US')[:2], 
            "User-Agent": "Odoo-Native-Client/1.0",
            "Connection": "close"
        }

        # إعداد متغير لتجميع تفاصيل السجل
        log_details = f"=== REQUEST ===\nURL: {method} {full_url}\n"
        if body:
            log_details += f"Body:\n{body}\n"
        else:
            log_details += "Body: [Empty]\n"

        try:
            _logger.info(f"⚡ Request: {method} {full_url}")
            if body:
                _logger.info(f"📦 Body: {body}")
            
            context = ssl._create_unverified_context()
            conn = http.client.HTTPSConnection(host, port=443, timeout=45, context=context)
            
            conn.request(method, path, body=body, headers=headers)
            
            response = conn.getresponse()
            response_data = response.read()
            conn.close()

            response_text = response_data.decode('utf-8')
            
            # إضافة الرد إلى السجل
            log_details += f"\n=== RESPONSE ===\nStatus: {response.status}\nBody:\n{response_text}"

            _logger.info(f"✨ Response Status: {response.status}")
            if response.status not in [200, 201]:
                 _logger.warning(f"⚠️ Response Error Body: {response_text}")

            if response.status in [200, 201]:
                # [LOG] تسجيل النجاح مع التفاصيل الكاملة
                self._log_call(endpoint, 'success', log_details)
                
                if not response_text.strip():
                     return {}
                return json.loads(response_text)
            else:
                # [LOG] تسجيل الخطأ مع التفاصيل الكاملة
                self._log_call(endpoint, 'error', log_details)
                
                msg = f"API Error {response.status} from [{full_url}]: {response_text}"
                raise UserError(msg)

        except Exception as e:
            # تسجيل أخطاء الاتصال (مثل التايم آوت أو انقطاع النت)
            log_details += f"\n\n=== EXCEPTION ===\n{str(e)}"
            self._log_call(endpoint, 'error', log_details)
            
            _logger.exception("Native HTTP Failed")
            raise UserError(str(e))