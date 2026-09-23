# Darbak Vehicle Hub

## أولوية الفرع الحالية: TPMS فقط

Firmware الفرع `tpms-esp32-priority` يفك إطار الحساس الحالي ويتحقق من
Manchester وSUM8. تحويل الضغط والحرارة ومعرّف الحساس النهائي ما زال يحتاج
ربطًا بقراءات مرجعية؛ لا يصدر قياسات مزيفة.
[التجربة الواحدة](docs/TPMS_FIELD_TEST.md) · [أدلة فك الإطار](docs/TPMS_DECODER.md).
الأقسام التالية تصف خطة المشروع الأوسع، ولا تعني تنفيذ هذه الخصائص في الفرع الحالي.

بوابة بيانات السيارة لمنظومة **دربك**، موجهة لشاشة السيارة Android 7.1 بدقة 1024×600.

## V1
- قراءة حساسات TPMS الخارجية على 433.92 MHz عبر ESP32 + CC1101.
- قراءة CAN/OBD عبر ESP32 TWAI + SN65HVD230، بوضع **Listen Only** افتراضيًا.
- إرسال Telemetry موحدة إلى Android عبر USB Serial.
- تطوير الواجهة والتطبيق في Simulator Mode قبل وصول القطع.
- التكامل لاحقًا مع Launcher 2026، دربك صيانة، التشخيص والتنبيهات.

## Darbak 2.0 UI
الواجهة تعتمد هوية دربك الجديدة: خلفية داكنة كحلية، أكسنت أزرق متوهج، بطاقات شبه شفافة، نص عربي واضح، وعناصر لمس كبيرة بدون شريط سفلي دائم.

## Safety defaults
- CAN transmit disabled by default.
- OBD pin 16 (+12V) is not used for ESP32 power in V1.
- ESP32 powered by Android head-unit USB.
- SN65HVD230 termination jumper must be open in the vehicle.
- CC1101 powered only from 3.3V.

## Serial protocol
One JSON object per line, UTF-8.

```json
{"v":1,"type":"tpms","pos":"FL","psi":34.7,"tempC":31,"battery":"ok","rssi":-63}
{"v":1,"type":"vehicle","speedKph":82,"rpm":1850,"coolantC":88,"voltage":14.1}
{"v":1,"type":"status","can":"listen_only","tpms":"scanning"}
```

See `PROJECT_DECISIONS.md` for the approved hardware, safety and identity decisions.
