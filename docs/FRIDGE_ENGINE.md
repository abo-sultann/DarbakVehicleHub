# Darbak Fridge Engine

## الهدف
طبقة موحدة داخل Darbak Vehicle Hub لدعم أكبر عدد ممكن من ثلاجات السيارات ذات التحكم المحلي عبر Bluetooth/BLE، بدون ربط واجهة التطبيق بعلامة تجارية واحدة.

## البنية
- Scanner / Auto Detect
- FridgeProtocol driver interface
- Unified FridgeState
- Drivers قابلة للإضافة
- أول Driver: Alpicool/OEM BLE family باستخدام GATT service 0x1234 و characteristics 0x1235/0x1236 للكشف فقط.

## قواعد الأمان والجودة
- لا توجد قراءة وهمية: غير المدعوم = غير متاح.
- لا نرسل أوامر تحكم غير مؤكدة إلى جهاز حقيقي.
- اكتشاف البروتوكول يعتمد على GATT characteristics وليس الاسم التجاري فقط.
- ICECO الحالية هي أول جهاز اختبار، وليست قيداً على المحرك.
- بعد فحص GATT الحقيقي نضيف Driver ICECO أو نثبت توافقها مع Alpicool/OEM.
- التشغيل/الإيقاف في واجهة شاشة السيارة يكون بضغط مطول.

## Unified capabilities
درجة الحرارة الحالية والمطلوبة، جهد الدخل، التشغيل، ECO/MAX، حماية البطارية، حالة الاتصال والأخطاء؛ كل خاصية تظهر فقط عند دعمها.
