import logging
import json
import urllib.parse
import http.client
import ssl
from odoo import models, api, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# القائمة المسموحة (تم التحديث لإضافة روابط الدفع والبحث الجديد)
ALLOWED_ENDPOINTS = [
    '/hotels/rates',
    '/hotels/details',
    '/rates',
    '/booking',
    '/rates/prebook',  # لدعم مرحلة Prebook الجديدة
    '/rates/book',     # لدعم مرحلة التثبيت النهائية
    '/data/cities',
    '/data/hotels',
    '/data/hotel',
    '/data/places'     # جديد: لدعم البحث بالأماكن (Place Search)
]

class LiteAPIClient(models.AbstractModel):
    _name = 'liteapi.client'
    _description = 'LiteAPI Client Service'

    @api.model
    def _get_config(self):
        """جلب إعدادات الاتصال من إعدادات النظام"""
        ICP = self.env['ir.config_parameter'].sudo()
        base_url = ICP.get_param('liteapi.base_url')
        api_key = ICP.get_param('liteapi.api_key')
        return base_url, api_key

    @api.model
    def _log_call(self, endpoint, result, details=""):
        """تسجيل العمليات في سجل التدقيق"""
        try:
            self.env['liteapi.audit.log'].sudo().create({
                'name': endpoint,
                'user_id': self.env.uid,
                'result': result,
                'details': details[:1000]
            })
        except:
            pass

    @api.model
    def check_safety(self, endpoint):
        """التحقق من أن الرابط المطلوب مسموح به"""
        is_allowed = False
        for allowed in ALLOWED_ENDPOINTS:
            # السماح بالتطابق التام أو البدء بالرابط (لدعم المتغيرات في الرابط)
            if endpoint == allowed or endpoint.startswith(allowed + '?') or endpoint.startswith(allowed + '/'):
                 is_allowed = True
                 break
        if not is_allowed:
            raise AccessError(_("BLOCKED: API Endpoint '%s' is not in the allowlist.") % endpoint)
        return True

    @api.model
    def make_request(self, endpoint, method='GET', **kwargs):
        """تنفيذ طلب HTTP آمن"""
        self.check_safety(endpoint)
        base_url, api_key = self._get_config()
        
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

        # معالجة المعاملات (Params)
        params = kwargs.get('params', {})
        if params:
            query_string = urllib.parse.urlencode(params)
            path = f"{path}?{query_string}"

        # معالجة جسم الطلب (Body)
        body = None
        if method.upper() == 'POST':
            json_payload = kwargs.get('json', {})
            body = json.dumps(json_payload)

        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Odoo-Native-Client/1.0",
            "Connection": "close"
        }

        try:
            _logger.info(f"⚡ Native HTTP Request to: https://{host}{path}")
            
            # إنشاء سياق SSL (غير مفعل التحقق للتطوير، يفضل تفعيله في الإنتاج)
            context = ssl._create_unverified_context()
            conn = http.client.HTTPSConnection(host, port=443, timeout=45, context=context)
            
            conn.request(method, path, body=body, headers=headers)
            
            response = conn.getresponse()
            response_data = response.read()
            conn.close()

            response_text = response_data.decode('utf-8')
            
            if response.status in [200, 201]:
                if not response_text.strip():
                     msg = f"Success (200) but Empty Body from: {full_url}"
                     _logger.error(msg)
                     raise UserError(msg)
                return json.loads(response_text)
            else:
                msg = f"API Error {response.status} from [{full_url}]: {response_text[:200]}"
                self._log_call(endpoint, 'error', msg)
                raise UserError(msg)

        except Exception as e:
            _logger.exception("Native HTTP Failed")
            raise UserError(f"Connection Failed to [{full_url}]: {str(e)}")