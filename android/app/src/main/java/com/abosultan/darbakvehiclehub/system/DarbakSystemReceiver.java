package com.abosultan.darbakvehiclehub.system;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * Private Darbak system responder.
 *
 * Vehicle Hub currently runs a telemetry simulator, so this responder deliberately reports a
 * degraded/simulation state and never exposes the simulated values to Darbak Launcher as real car
 * telemetry.
 */
public final class DarbakSystemReceiver extends BroadcastReceiver {
    private static final int SCHEMA_VERSION = 1;
    private static final String ACTION_STATUS_REQUEST = "com.abosultan.darbak.system.STATUS_REQUEST";
    private static final String ACTION_STATUS_RESPONSE = "com.abosultan.darbak.system.STATUS_RESPONSE";
    private static final String LAUNCHER_PACKAGE = "com.aistudio.carlauncher.lzrk26";

    private static final String EXTRA_SCHEMA_VERSION = "darbak_schema_version";
    private static final String EXTRA_REQUEST_ID = "darbak_request_id";
    private static final String EXTRA_MODULE_ID = "darbak_module_id";
    private static final String EXTRA_HEALTH = "darbak_health";
    private static final String EXTRA_PRIMARY_TEXT = "darbak_primary_text";
    private static final String EXTRA_SECONDARY_TEXT = "darbak_secondary_text";
    private static final String EXTRA_METRIC_VALUE = "darbak_metric_value";
    private static final String EXTRA_METRIC_UNIT = "darbak_metric_unit";
    private static final String EXTRA_TIMESTAMP_MS = "darbak_timestamp_ms";

    @Override public void onReceive(Context context, Intent intent) {
        if (intent == null || !ACTION_STATUS_REQUEST.equals(intent.getAction())) return;

        Intent response = new Intent(ACTION_STATUS_RESPONSE);
        response.setPackage(LAUNCHER_PACKAGE);
        response.putExtra(EXTRA_SCHEMA_VERSION, SCHEMA_VERSION);
        response.putExtra(EXTRA_REQUEST_ID, intent.getStringExtra(EXTRA_REQUEST_ID));
        response.putExtra(EXTRA_MODULE_ID, "VEHICLE_HUB");
        response.putExtra(EXTRA_HEALTH, "degraded");
        response.putExtra(EXTRA_PRIMARY_TEXT, "وضع محاكاة");
        response.putExtra(EXTRA_SECONDARY_TEXT, "لا توجد قراءة سيارة فعلية");
        response.putExtra(EXTRA_METRIC_VALUE, "");
        response.putExtra(EXTRA_METRIC_UNIT, "");
        response.putExtra(EXTRA_TIMESTAMP_MS, System.currentTimeMillis());
        context.sendBroadcast(response);
    }
}
