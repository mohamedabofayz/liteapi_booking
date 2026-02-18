# آلية عمل نظام الحجز الفندقي في وحدة LiteAPI Booking

## لمحة عامة

نظام الحجز الفندقي في وحدة LiteAPI Booking يتبع عملية متكاملة من البحث عن الفنادق إلى إتمام الحجز النهائي. العملية تعتمد على واجهة برمجة تطبيقات (API) من LiteAPI وتتكون من عدة مراحل رئيسية.

## مراحل عملية الحجز

### 1. مرحلة البحث عن الأسعار الدنيا لل-hotels (min-rates)

في هذه المرحلة، يتم إرسال طلب POST إلى واجهة برمجة التطبيقات للحصول على أقل أسعار الفنادق المتاحة.

#### تفاصيل الطلب:
- **الرابط**: `https://api.liteapi.travel/v3.0/hotels/min-rates`
- **Headers**:
  - `accept`: `application/json`
  - `content-type`: `application/json`
  - `X-API-Key`: مفتاح API الخاص بالمستخدم

#### بيانات الطلب (Payload):
- `checkin`: تاريخ الدخول (مثلاً: "2026-03-20")
- `checkout`: تاريخ الخروج (مثلاً: "2026-03-28")
- `currency`: العملة (مثلاً: "SAR")
- `guestNationality`: جنسية الضيف (مثلاً: "SA")
- `timeout`: مهلة الطلب (مثلاً: 10)
- `hotelIds`: مصفوفة تحتوي على معرفات الفنادق المطلوبة (مثلاً: ["lp62b6c"])
- `occupancies`: مصفوفة تحتوي على تفاصيل الأشغال (مثلاً: [{"adults": 2}])

#### نموذج الرد:
```json
{
  "data": [
    {
      "hotelId": "lp62b6c",
      "price": 838.76,
      "suggestedSellingPrice": 799.88,
      "offerId": "3gAVonJzkY2kc3JpZNoBIEc0WlRPTkJXR0UzR0tOUlVHWVlUT01SV0dRWkRBTlpVRzQzVE1PSldNVVpEQU5aU0daVERNWlJXTVI2RENJWlNHQVpETU1CVEdJWUhZTVJRR0kzREFNWlNIQjZHSzNTN0tWSlhZVTJCUFJKVUNVVDRHSkFUQVEzNEdJWkRRTTM0S1VaRk1XRFNQUVlUT05aUkdRWVRRTkpVR01ZVFFPS1VLUk1VWUlaVUdBMkRHTVpTRU1ZVEVNSlhGVTJEQU5CVEdNWkhZVFNTSVpISFlNUlFHSTNEQU1SUkc0WURTTkpaUFFZWFlVUlJHQTJEUzdCWEdZWkRLTUpES0pIU0dUU1NJWkhDR01SUUdJM0MyTUJTRlVZVE9JQlFIRTVES09KRKNwcmPLQIo2FHrhR66lb3JfcHLLAAAAAAAAAACiY23LAAAAAAAAAACjcGNkoKNicmSiUk-kbXJpZMCjbXJuwKNoZHDAo2ZybqCjc3JuslN0YW5kYXJkIFR3aW4gUm9vbaNvY24BpHBya3PApHNoaWSmNDA0MzMyo3NpZAKjaGlkp2xwNjJiNmOjb2NjkYGhYQKjY3Vyo1NBUqJnbqJTQaJjaaoyMDI2LTAzLTIwomNvqjIwMjYtMDMtMjijZ2lkoKJjcstAJAAAAAAAAKRzc2lk2TBzZXNzaW9uXzAxOWM3MGM1ZTQ0OElZQ2JGc0NXcWFxNEZXdUt4ZkYwTW9KSERKY06jaXNowqNzc3CucHJvdmlkZXJEaXJlY3SjaWZtwqVpZmNocsKlc2VhaWSgom5rwKJ0eJGEoWnDoWSjVGF4oWHLQGBgo9cKPXGhY6NTQVKibHDAo2JrdAE="
    }
  ],
  "sandbox": true
}
```

### 2. مرحلة حجز مسبق (prebook)

بعد الحصول على `offerId` من المرحلة الأولى، يتم إرسال طلب حجز مسبق للتحقق من توفر الغرفة وتأمين السعر.

#### تفاصيل الطلب:
- **الرابط**: `https://book.liteapi.travel/v3.0/rates/prebook`
- **Parameters**:
  - `timeout`: 30
  - `includeCreditBalance`: false
- **Headers**:
  - `accept`: `application/json`
  - `content-type`: `application/json`
  - `X-API-Key`: مفتاح API

#### بيانات الطلب (Payload):
- `usePaymentSdk`: true
- `offerId`: المعرف الذي تم الحصول عليه من مرحلة البحث
- `includeCreditBalance`: false

#### نموذج الرد:
```json
{
  "data": {
    "prebookId": "a4KVohKE4",
    "offerId": "3gAVonJzkY2kc3JpZNoBIEc0WlRPTkJXR0UzR0tOUlVHWVlUT01SV0dRWkRBTlpVRzQzVE1PSldNVVpEQU5aU0daVERNWlJXTVI2RENJWlNHQVpETU1CVEdJWUhZTVJRR0kzREFNWlNIQjZHSzNTN0tWSlhZVTJCUFJKVUNVVDRHSkFUQVEzNEdJWkRRTTM0S1VaRk1XRFNQUVlUT05aUkdRWVRRTkpVR01ZVFFPS1VLUk1VWUlaVUdBMkRHTVpTRU1ZVEVNSlhGVTJEQU5CVEdNWkhZVFNTSVpISFlNUlFHSTNEQU1SUkc0WURTTkpaUFFZWFlVUlJHQTJEUzdCWEdZWkRLTUpES0pIU0dUU1NJWkhDR01SUUdJM0MyTUJTRlVZVE9JQlFIRTVES09KRKNwcmPLQIo2FHrhR66lb3JfcHLLAAAAAAAAAACiY23LAAAAAAAAAACjcGNkoKNicmSiUk-kbXJpZMCjbXJuwKNoZHDAo2ZybqCjc3JuslN0YW5kYXJkIFR3aW4gUm9vbaNvY24BpHBya3PApHNoaWSmNDA0MzMyo3NpZAKjaGlkp2xwNjJiNmOjb2NjkYGhYQKjY3Vyo1NBUqJnbqJTQaJjaaoyMDI2LTAzLTIwomNvqjIwMjYtMDMtMjijZ2lkoKJjcstAJAAAAAAAAKRzc2lk2TBzZXNzaW9uXzAxOWM3MGM1ZTQ0OElZQ2JGc0NXcWFxNEZXdUt4ZkYwTW9KSERKY06jaXNowqNzc3CucHJvdmlkZXJEaXJlY3SjaWZtwqVpZmNocsKlc2VhaWSgom5rwKJ0eJGEoWnDoWSjVGF4oWHLQGBgo9cKPXGhY6NTQVKibHDAo2JrdAE=",
    "hotelId": "lp62b6c",
    "currency": "SAR",
    "transactionId": "tr_cts_wWj5F4NaMsn8Ysdw-jqE_",
    "secretKey": "pi_3T2A72A4FXPoRk9Y0ZSIYSYC_secret_djn6vvqLD8q0fdKiMlIq7qekl"
  }
}
```

## التكامل مع واجهة المستخدم

### 1. واجهة البحث
- تتيح للمستخدم إدخال تفاصيل الحجز (تواريخ، عدد الأشخاص، جنسية الضيف)
- ترسل هذه البيانات إلى وحدة البحث للحصول على نتائج الفنادق

### 2. واجهة تفاصيل الفندق
- تعرض معلومات مفصلة عن الفندق
- تتيح للمستخدم رؤية الأسعار والغرف المتاحة

### 3. واجهة الحجز
- تسمح بإتمام عملية الحجز بعد اختيار الغرف المناسبة
- تتعامل مع مزودي الدفع من خلال معلومات الحجز

## مكونات النظام

### 1. نماذج البيانات
- `booking`: يحتوي على معلومات الحجز الأساسية
- `search_template`: يحتوي على قوالب البحث المحفوظة
- `hotel`: يحتوي على معلومات الفنادق
- `city/country`: يحتوي على معلومات الموقع الجغرافي

### 2. وحدات التحكم
- `booking_controller`: يدير عمليات الحجز
- `hotel_controller`: يتحكم في عرض معلومات الفنادق
- `checkout_controller`: يتعامل مع عملية الدفع
- `details_controller`: يعرض تفاصيل الحجز

### 3. واجهات العرض
- قوالب بوابة المستخدم
- نماذج البحث
- صفحات تفاصيل الحجز

## الأمان والجودة

- تحقق من صحة مفاتيح API
- تأمين الاتصالات مع واجهة البرمجة
- التحقق من صحة البيانات المدخلة
- التسجيل التفصيلي للأحداث
- التكامل مع أنظمة Cron لمراقبة الحجوزات

## الاستخدام العملي

1. يبدأ المستخدم ببحث عن فندق عبر واجهة البحث
2. النظام يستعلم عن الأسعار من خلال واجهة min-rates
3. بعد اختيار سعر مناسب، يتم إنشاء حجز مسبق باستخدام prebook
4. يتم حفظ معلومات الحجز في قاعدة البيانات
5. عند إتمام الدفع، يتم تحويل الحجز المسبق إلى حجز رسمي
6. يتم تتبع حالة الحجز حتى اكتماله أو إلغائه

## ملاحظات هامة

- يجب دائمًا التحقق من حالة الحجز (مفعل، ملغى، مؤكد)
- يجب معالجة أخطاء API بشكل مناسب
- يجب تخزين معلومات الحجز المؤقتة بشكل آمن
- يجب تحديث حالة الحجز عند تغييرات السعر أو التوافر