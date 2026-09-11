package com.abosultan.darbakvehiclehub.ui;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.TextView;

import com.abosultan.darbakvehiclehub.R;

import java.util.Locale;

public final class MainActivity extends Activity {
    private final Handler handler = new Handler();
    private float flPsi = 34.6f;
    private float frPsi = 34.8f;
    private float rlPsi = 34.1f;
    private float rrPsi = 35.0f;
    private int tick = 0;

    private TextView flPsiView;
    private TextView frPsiView;
    private TextView rlPsiView;
    private TextView rrPsiView;
    private TextView speedView;
    private TextView rpmView;
    private TextView coolantView;
    private TextView voltageView;
    private TextView healthTitle;
    private TextView healthDetail;

    private final Runnable simulator = new Runnable() {
        @Override public void run() {
            tick++;
            flPsi -= 0.02f;
            if (flPsi < 33.8f) flPsi = 34.6f;
            int speed = 78 + (tick % 9);
            int rpm = 1760 + ((tick * 37) % 260);
            int coolant = 87 + ((tick / 8) % 2);
            float voltage = 14.0f + ((tick % 3) * 0.05f);

            bindTpms(flPsi, frPsi, rlPsi, rrPsi);
            bindVehicle(speed, rpm, coolant, voltage);
            bindHealth(flPsi);
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

        flPsiView = findViewById(R.id.flPsi);
        frPsiView = findViewById(R.id.frPsi);
        rlPsiView = findViewById(R.id.rlPsi);
        rrPsiView = findViewById(R.id.rrPsi);
        speedView = findViewById(R.id.speedValue);
        rpmView = findViewById(R.id.rpmValue);
        coolantView = findViewById(R.id.coolantValue);
        voltageView = findViewById(R.id.voltageValue);
        healthTitle = findViewById(R.id.healthTitle);
        healthDetail = findViewById(R.id.healthDetail);

        bindTpms(flPsi, frPsi, rlPsi, rrPsi);
        bindVehicle(82, 1850, 88, 14.1f);
        bindHealth(flPsi);
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

    private void bindTpms(float fl, float fr, float rl, float rr) {
        flPsiView.setText(oneDecimal(fl));
        frPsiView.setText(oneDecimal(fr));
        rlPsiView.setText(oneDecimal(rl));
        rrPsiView.setText(oneDecimal(rr));
    }

    private void bindVehicle(int speedKph, int rpm, int coolantC, float voltage) {
        speedView.setText(String.valueOf(speedKph));
        rpmView.setText(String.valueOf(rpm));
        coolantView.setText(coolantC + "°");
        voltageView.setText(oneDecimal(voltage));
    }

    private void bindHealth(float lowestPsi) {
        if (lowestPsi < 30.0f) {
            healthTitle.setText("تنبيه ضغط الإطار");
            healthTitle.setTextColor(getResources().getColor(R.color.danger));
            healthDetail.setText("تم رصد ضغط منخفض ويحتاج فحصًا");
        } else {
            healthTitle.setText("الحالة طبيعية");
            healthTitle.setTextColor(getResources().getColor(R.color.success));
            healthDetail.setText("لا توجد تنبيهات • المحاكاة تعمل");
        }
    }

    private static String oneDecimal(float value) {
        return String.format(Locale.US, "%.1f", value);
    }
}
