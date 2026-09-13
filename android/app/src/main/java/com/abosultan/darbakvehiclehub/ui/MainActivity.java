package com.abosultan.darbakvehiclehub.ui;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
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
    private TextView tpmsSummary;

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

        render(System.currentTimeMillis());
    }

    @Override protected void onResume() {
        super.onResume();
        handler.removeCallbacks(simulator);
        handler.post(simulator);
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
        if (reading.isAvailable(now)) {
            valueView.setText(reading.value + "\n" + reading.source.label());
        } else {
            valueView.setText("—\nغير متاح");
        }
    }

    private void bindFloatInValue(TextView valueView, TelemetryState.FloatReading reading, long now) {
        if (reading.isAvailable(now)) {
            valueView.setText(oneDecimal(reading.value) + "\n" + reading.source.label());
        } else {
            valueView.setText("—\nغير متاح");
        }
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

    private void showDiagnostics() {
        long now = System.currentTimeMillis();
        StringBuilder text = new StringBuilder();
        text.append("حالة CAN: ")
                .append(lastFrameAtMs > 0L && now - lastFrameAtMs <= TelemetryState.DEFAULT_STALE_AFTER_MS ? "متصل/محاكاة" : "غير متصل")
                .append('\n');
        text.append("آخر إطار: ").append(formatTime(lastFrameAtMs)).append('\n');
        text.append("حساسات TPMS المكتشفة: ").append(availableTpmsCount(now)).append(" / 4\n\n");
        text.append("سرعة السيارة: ").append(readingDiagnostic(telemetry.vehicleSpeedKph, now)).append('\n');
        text.append("CAN الخام: ").append(readingDiagnostic(telemetry.rawCanSpeedKph, now)).append('\n');
        text.append("GPS: ").append(readingDiagnostic(telemetry.gpsSpeedKph, now)).append('\n');
        text.append("السرعة المصححة: ").append(readingDiagnostic(telemetry.correctedSpeedKph, now)).append('\n');
        text.append("RPM: ").append(readingDiagnostic(telemetry.rpm, now)).append('\n');
        text.append("حرارة المحرك: ").append(readingDiagnostic(telemetry.coolantC, now)).append('\n');
        text.append("الفولت: ").append(readingDiagnostic(telemetry.voltage, now)).append("\n\n");
        text.append("آخر خطأ: ").append(lastError);

        new AlertDialog.Builder(this)
                .setTitle("تشخيص Darbak Vehicle Hub")
                .setMessage(text.toString())
                .setPositiveButton("إغلاق", null)
                .show();
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
