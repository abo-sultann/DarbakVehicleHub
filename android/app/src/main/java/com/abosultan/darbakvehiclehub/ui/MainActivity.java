package com.abosultan.darbakvehiclehub.ui;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.Manifest;
import android.content.pm.PackageManager;
import com.abosultan.darbakvehiclehub.fridge.FridgeBleManager;
import com.abosultan.darbakvehiclehub.update.UpdateManager;
import android.os.Handler;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.TextView;

import com.abosultan.darbakvehiclehub.R;
import com.abosultan.darbakvehiclehub.data.TelemetryState;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public final class MainActivity extends Activity {
    private final Handler handler = new Handler();
    private final TelemetryState telemetry = new TelemetryState();

    private float flPsiSim = 34.6f;
    private int tick = 0;
    private long lastFrameAtMs = 0L;
    private String lastError = "لا يوجد";

    private TextView flPsiView;
    private TextView frPsiView;
    private TextView rlPsiView;
    private TextView rrPsiView;
    private TextView flMetaView;
    private TextView frMetaView;
    private TextView rlMetaView;
    private TextView rrMetaView;
    private TextView speedView;
    private TextView rpmView;
    private TextView coolantView;
    private TextView voltageView;
    private TextView healthTitle;
    private TextView healthDetail;
    private TextView chipCan;
    private TextView chipTpms;
    private TextView chipFridge;
    private TextView chipUpdate;
    private UpdateManager updateManager;
    private TextView tpmsSummary;
    private FridgeBleManager fridgeBle;
    private String fridgeStatus = "غير متصلة";
    private String fridgeDevice = "—";
    private String fridgeGatt = "—";
    private String fridgeProtocol = "—";
    private AlertDialog fridgeDialog;

    private final Runnable simulator = new Runnable() {
        @Override public void run() {
            tick++;
            flPsiSim -= 0.02f;
            if (flPsiSim < 33.8f) flPsiSim = 34.6f;

            long now = System.currentTimeMillis();
            int speed = 78 + (tick % 9);
            int rpm = 1760 + ((tick * 37) % 260);
            int coolant = 87 + ((tick / 8) % 2);
            float voltage = 14.0f + ((tick % 3) * 0.05f);

            telemetry.set(telemetry.flPsi, flPsiSim, TelemetryState.Source.SIMULATION, now);
            telemetry.set(telemetry.frPsi, 34.8f, TelemetryState.Source.SIMULATION, now);
            telemetry.set(telemetry.rlPsi, 34.1f, TelemetryState.Source.SIMULATION, now);
            telemetry.set(telemetry.rrPsi, 35.0f, TelemetryState.Source.SIMULATION, now);
            telemetry.set(telemetry.vehicleSpeedKph, speed, TelemetryState.Source.SIMULATION, now);
            telemetry.set(telemetry.rawCanSpeedKph, speed, TelemetryState.Source.SIMULATION, now);
            telemetry.set(telemetry.rpm, rpm, TelemetryState.Source.SIMULATION, now);
            telemetry.set(telemetry.coolantC, coolant, TelemetryState.Source.SIMULATION, now);
            telemetry.set(telemetry.voltage, voltage, TelemetryState.Source.SIMULATION, now);
            lastFrameAtMs = now;

            render(now);
            handler.postDelayed(this, 1000L);
        }
    };

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN |
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY |
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION |
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        setContentView(R.layout.activity_main);

        bindViews();
        chipCan.setOnLongClickListener(new View.OnLongClickListener() {
            @Override public boolean onLongClick(View v) {
                showDiagnostics();
                return true;
            }
        });

        chipFridge.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                if (fridgeBle != null && fridgeBle.bluetoothState() == 1) {
                    fridgeBle.requestEnableBluetooth();
                } else {
                    showFridgeStatus();
                }
            }
        });
        updateManager = new UpdateManager(this);
        chipUpdate.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { updateManager.check(); }
        });

        fridgeBle = new FridgeBleManager(this, new FridgeBleManager.Listener() {
            @Override public void onStatus(final String s) { runOnUiThread(new Runnable(){ @Override public void run(){ fridgeStatus=s; chipFridge.setText("❄ الثلاجة • "+s); refreshFridgeDialog(); }}); }
            @Override public void onDevice(final String n) { runOnUiThread(new Runnable(){@Override public void run(){fridgeDevice=n; refreshFridgeDialog();}}); }
            @Override public void onGattProfile(final String p) { runOnUiThread(new Runnable(){@Override public void run(){fridgeGatt=p; refreshFridgeDialog();}}); }
            @Override public void onProtocol(final String p) { runOnUiThread(new Runnable(){@Override public void run(){fridgeProtocol=p; refreshFridgeDialog();}}); }
        });
        render(System.currentTimeMillis());
    }

    @Override protected void onResume() {
        super.onResume();
        handler.removeCallbacks(simulator);
        handler.post(simulator);
    }

    @Override protected void onDestroy() { if (fridgeBle != null) fridgeBle.close(); super.onDestroy(); }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == 701 && results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED && fridgeBle != null) fridgeBle.startScan();
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, android.content.Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == 702 && fridgeBle != null) {
            if (fridgeBle.bluetoothState() == 2) { fridgeBle.startScan(); refreshFridgeDialog(); }
            else { fridgeStatus = "Bluetooth ما زال متوقفًا"; refreshFridgeDialog(); }
        }
    }

    @Override protected void onPause() {
        handler.removeCallbacks(simulator);
        super.onPause();
    }

    private void bindViews() {
        flPsiView = findViewById(R.id.flPsi);
        frPsiView = findViewById(R.id.frPsi);
        rlPsiView = findViewById(R.id.rlPsi);
        rrPsiView = findViewById(R.id.rrPsi);
        flMetaView = findViewById(R.id.flMeta);
        frMetaView = findViewById(R.id.frMeta);
        rlMetaView = findViewById(R.id.rlMeta);
        rrMetaView = findViewById(R.id.rrMeta);
        speedView = findViewById(R.id.speedValue);
        rpmView = findViewById(R.id.rpmValue);
        coolantView = findViewById(R.id.coolantValue);
        voltageView = findViewById(R.id.voltageValue);
        healthTitle = findViewById(R.id.healthTitle);
        healthDetail = findViewById(R.id.healthDetail);
        chipCan = findViewById(R.id.chipCan);
        chipTpms = findViewById(R.id.chipTpms);
        chipFridge = findViewById(R.id.chipFridge);
        chipUpdate = findViewById(R.id.chipUpdate);
        tpmsSummary = findViewById(R.id.tpmsSummary);
    }

    private void render(long now) {
        bindFloat(flPsiView, flMetaView, telemetry.flPsi, "PSI", now);
        bindFloat(frPsiView, frMetaView, telemetry.frPsi, "PSI", now);
        bindFloat(rlPsiView, rlMetaView, telemetry.rlPsi, "PSI", now);
        bindFloat(rrPsiView, rrMetaView, telemetry.rrPsi, "PSI", now);

        bindIntInValue(speedView, telemetry.vehicleSpeedKph, now);
        bindIntInValue(rpmView, telemetry.rpm, now);
        bindIntInValue(coolantView, telemetry.coolantC, now);
        bindFloatInValue(voltageView, telemetry.voltage, now);

        int tpmsCount = availableTpmsCount(now);
        tpmsSummary.setText(tpmsCount + " / 4 متصل");
        chipTpms.setText("TPMS  •  " + (tpmsCount > 0 ? telemetry.flPsi.source.label() : "غير متاح"));

        boolean frameFresh = lastFrameAtMs > 0L && now - lastFrameAtMs <= TelemetryState.DEFAULT_STALE_AFTER_MS;
        chipCan.setText(frameFresh ? "CAN  •  جاهز للاستماع" : "CAN  •  غير متصل");

        if (!frameFresh) {
            healthTitle.setText("البيانات غير متاحة");
            healthTitle.setTextColor(getResources().getColor(R.color.danger));
            healthDetail.setText("لا توجد قراءة حديثة • لن يتم عرض آخر قيمة كأنها حية");
            return;
        }

        float lowest = lowestAvailablePsi(now);
        if (!Float.isNaN(lowest) && lowest < 30.0f) {
            healthTitle.setText("تنبيه ضغط الإطار");
            healthTitle.setTextColor(getResources().getColor(R.color.danger));
            healthDetail.setText("تم رصد ضغط منخفض ويحتاج فحصًا");
        } else {
            healthTitle.setText("الحالة طبيعية");
            healthTitle.setTextColor(getResources().getColor(R.color.success));
            healthDetail.setText("لا توجد تنبيهات • المصدر ظاهر مع كل قراءة");
        }
    }

    private void bindFloat(TextView valueView, TextView metaView,
                           TelemetryState.FloatReading reading, String unit, long now) {
        if (reading.isAvailable(now)) {
            valueView.setText(oneDecimal(reading.value));
            metaView.setText(unit + " • " + reading.source.label());
        } else {
            valueView.setText("—");
            metaView.setText(unit + " • غير متاح");
        }
    }

    private void bindIntInValue(TextView valueView, TelemetryState.IntReading reading, long now) {
        if (reading.isAvailable(now)) valueView.setText(reading.value + " • " + reading.source.label());
        else valueView.setText("— • غير متاح");
    }

    private void bindFloatInValue(TextView valueView, TelemetryState.FloatReading reading, long now) {
        if (reading.isAvailable(now)) valueView.setText(oneDecimal(reading.value) + " • " + reading.source.label());
        else valueView.setText("— • غير متاح");
    }

    private int availableTpmsCount(long now) {
        int count = 0;
        if (telemetry.flPsi.isAvailable(now)) count++;
        if (telemetry.frPsi.isAvailable(now)) count++;
        if (telemetry.rlPsi.isAvailable(now)) count++;
        if (telemetry.rrPsi.isAvailable(now)) count++;
        return count;
    }

    private float lowestAvailablePsi(long now) {
        float lowest = Float.NaN;
        TelemetryState.FloatReading[] readings = {
                telemetry.flPsi, telemetry.frPsi, telemetry.rlPsi, telemetry.rrPsi
        };
        for (TelemetryState.FloatReading reading : readings) {
            if (!reading.isAvailable(now)) continue;
            if (Float.isNaN(lowest) || reading.value < lowest) lowest = reading.value;
        }
        return lowest;
    }

    private void showFridgeStatus() {
        if (fridgeDialog == null || !fridgeDialog.isShowing()) {
            fridgeDialog = new AlertDialog.Builder(this)
                    .setTitle("❄ الثلاجة • تشخيص الاتصال")
                    .setMessage(fridgeMessage())
                    .setNegativeButton("إغلاق", null)
                    .setPositiveButton("إعادة البحث", null)
                    .create();
            fridgeDialog.setOnShowListener(new android.content.DialogInterface.OnShowListener() {
                @Override public void onShow(android.content.DialogInterface dialog) {
                    fridgeDialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(new View.OnClickListener() {
                        @Override public void onClick(View v) { startFridgeDiscovery(); }
                    });
                }
            });
            fridgeDialog.show();
            TextView messageView = fridgeDialog.findViewById(android.R.id.message);
            if (messageView != null) { messageView.setTextSize(16f); messageView.setTextIsSelectable(true); messageView.setLineSpacing(2f, 1.05f); }
        }
        startFridgeDiscovery();
    }

    private void startFridgeDiscovery() {
        if (fridgeBle == null) return;
        if (!fridgeBle.hasLocationPermission()) {
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, 701);
            return;
        }
        if (fridgeBle.bluetoothState() == 1) {
            fridgeBle.requestEnableBluetooth();
            return;
        }
        fridgeBle.startScan();
    }

    private String fridgeMessage() {
        String nl = System.getProperty("line.separator");
        return "الحالة: " + fridgeStatus
                + nl + "الجهاز: " + fridgeDevice
                + nl + "البروتوكول: " + fridgeProtocol
                + nl + nl + "GATT المكتشف:" + nl + fridgeGatt
                + nl + nl + "الاكتشاف آمن/قراءة فقط حتى اعتماد البروتوكول.";
    }

    private void refreshFridgeDialog() {
        if (fridgeDialog != null && fridgeDialog.isShowing()) fridgeDialog.setMessage(fridgeMessage());
    }

    private void showDiagnostics() {
        long now = System.currentTimeMillis();
        String nl = System.getProperty("line.separator");
        StringBuilder text = new StringBuilder();
        text.append("حالة CAN: ")
                .append(lastFrameAtMs > 0L && now - lastFrameAtMs <= TelemetryState.DEFAULT_STALE_AFTER_MS ? "متصل/محاكاة" : "غير متصل").append(nl);
        text.append("آخر إطار: ").append(formatTime(lastFrameAtMs)).append(nl);
        text.append("حساسات TPMS المكتشفة: ").append(availableTpmsCount(now)).append(" / 4").append(nl).append(nl);
        text.append("سرعة السيارة: ").append(readingDiagnostic(telemetry.vehicleSpeedKph, now)).append(nl);
        text.append("CAN الخام: ").append(readingDiagnostic(telemetry.rawCanSpeedKph, now)).append(nl);
        text.append("GPS: ").append(readingDiagnostic(telemetry.gpsSpeedKph, now)).append(nl);
        text.append("السرعة المصححة: ").append(readingDiagnostic(telemetry.correctedSpeedKph, now)).append(nl);
        text.append("RPM: ").append(readingDiagnostic(telemetry.rpm, now)).append(nl);
        text.append("حرارة المحرك: ").append(readingDiagnostic(telemetry.coolantC, now)).append(nl);
        text.append("الفولت: ").append(readingDiagnostic(telemetry.voltage, now)).append(nl).append(nl);
        text.append("آخر خطأ: ").append(lastError);
        new AlertDialog.Builder(this).setTitle("تشخيص Darbak Vehicle Hub")
                .setMessage(text.toString()).setPositiveButton("إغلاق", null).show();
    }

    private static String readingDiagnostic(TelemetryState.IntReading reading, long now) {
        if (!reading.isAvailable(now)) return "غير متاح";
        return reading.value + " • " + reading.source.label() + " • " + ageText(now - reading.updatedAtMs);
    }

    private static String readingDiagnostic(TelemetryState.FloatReading reading, long now) {
        if (!reading.isAvailable(now)) return "غير متاح";
        return oneDecimal(reading.value) + " • " + reading.source.label() + " • " + ageText(now - reading.updatedAtMs);
    }

    private static String ageText(long ageMs) {
        if (ageMs < 0L) ageMs = 0L;
        return "منذ " + (ageMs / 1000L) + "ث";
    }

    private static String formatTime(long timeMs) {
        if (timeMs <= 0L) return "لا يوجد";
        return new SimpleDateFormat("HH:mm:ss", Locale.US).format(new Date(timeMs));
    }

    private static String oneDecimal(float value) {
        return String.format(Locale.US, "%.1f", value);
    }
}
