# اختبار ضغط الإطارات وحرارتها عبر OBD

اختبار تشخيص مستقل عن حساس CC1101 الخارجي. مخصص لتجربة طلبات TPMS من عائلة تويوتا على فورتشنر 2020 ديزل؛ لم يثبت توافق هذه الطلبات مع هذه السيارة بعد.

## جلسة واحدة

1. استخدم توصيل ESP32 + SN65HVD230 السابق، وتغذية ESP32 من USB.
   هذا البناء يستخدم GPIO21 إلى TX/D، وGPIO22 إلى RX/R، وCAN بسرعة 500 kbit/s.
   إن كان توصيل التجربة السابقة على أرجل مختلفة، لا تبدل الأسلاك بالتخمين.
2. السيارة واقفة، القير P وفرامل الوقوف، والسويتش ON. أغلق أي جهاز تشخيص آخر.
   لا تضغط زر معايرة الإطارات ولا تغير ضغطها؛ لا تحتاج فصل حساسات الوكالة.
3. استخرج حزمة **DarbakVehicleHub-ESP32-OBD-TPMS** ثم شغّل:
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\Test-OBD-TPMS.ps1`
4. ينتهي خلال نحو ثلاث دقائق بعد التفليش. Ctrl+C ينهي الجلسة ويحفظها مبكرًا.
5. أرسل ملف `TPMS_OBD_*.zip` الذي يظهر على سطح المكتب؛ يتضمن كل الطلبات والردود وأوقاتها والملخص.

الحزمة تفلش قسم التطبيق فقط فوق تثبيت ESP32 السابق، وليس لوحة جديدة فارغة.
يمكن الرجوع لاختبار الحساس الخارجي بتشغيل حزمة Test-TPMS السابقة.

## What this test actually establishes

A dedicated firmware environment (`esp32_obd_tpms`) leaves the RF decoder source and fixtures intact.
No CAN transmission at boot: listen-only preflight must receive 20 clean CAN frames before START.
The host verifies firmware identity before START. Read-local-identifier requests are limited to
CAN ID 0x750, extended address 0x2A, service 0x21, identifiers 0x30 (pressure candidate) and
0x16 (temperature candidate), alternating every 3 seconds. Response CAN ID is 0x758.
ISO-TP flow control is `2A 30 00 0A 00 00 00 00` and sent only for an expected, bounded first frame.
There are no write, reset, learn, actuator, security-access, ABS or general PID scan commands.
Single-shot transmission avoids unlimited CAN retries. CAN errors, another 0x750 tester,
host STOP, four-second heartbeat expiry or the 180-second device limit stop the driver.
The host's normal limit is 175 seconds. Firmware is disarmed after termination until reset.

All physical values and Sensor ID remain null. Responses are shown as raw candidate payloads;
the firmware does not infer pressure from ABS speed or substitute engine temperatures.
Known 5-slot reply layouts are identified in the report without assuming wheel positions.
A successful ECU response may contain old sensor readings; its timestamp is the diagnostic
reception time, not proof of a new RF transmission. Missing replies do not prove TPMS absence.

## Source evidence and limits

OBDb contributors, Toyota-RAV4, revision `5063f49433d3f497e60e3f8d8ac14e8a20984d6c`:
- https://github.com/OBDb/Toyota-RAV4/blob/5063f49433d3f497e60e3f8d8ac14e8a20984d6c/signalsets/v3/default.json
- `tests/test_cases/2023/commands/750.758.2116|e=2A,fc=1.yaml`
- `tests/test_cases/2023/commands/750.758.2130|e=2A,ta=2A,fc=1.yaml`

The source documents temperature raw-40 C and pressure raw/58-0.5 bar on supported RAV4
variants. These formulas are **not enabled** for this unverified Fortuner. Two short recorded
reply examples are used in transport tests, attributed to OBDb contributors under CC BY-SA 4.0:
https://creativecommons.org/licenses/by-sa/4.0/ . The test adapts the examples into byte arrays.

The product advertisement previously reviewed describes ABS-based indirect monitoring;
it is not evidence for these diagnostic requests. This experiment tests a different route:
a direct request to the candidate Toyota TPMS ECU.

## Wiring note

OBD CAN-H is pin 6, CAN-L pin 14; verify pin numbering rather than seller wire colors.
Never connect OBD pin 16 (vehicle supply) to ESP32 GPIO/3.3V. The vehicle bus already has
termination; the add-on board must not add another 120-ohm terminator. The yellow plastic
on the seller's board photo does not establish the state of its 121 resistor.

## Offline checks

`python firmware/tests/test_obd.py` exercises the production ISO-TP receiver with recorded
multi-frame replies and malformed/foreign/truncated/out-of-order/late traffic. Candidate
classification checks ensure zero values and cross-model mappings never become measurements.
The existing RF replay suite remains a separate required CI gate. A passing build is not
a successful vehicle test.
