package com.abosultan.darbakvehiclehub.data;

/**
 * Normalized in-memory vehicle telemetry.
 *
 * Every value carries its real source and last-update time so the UI can avoid
 * presenting stale data as if it were live. Hardware adapters (CAN, TPMS,
 * external sensors, GPS) should write through the setter methods only.
 */
public final class TelemetryState {
    public enum Source {
        CAN("CAN حقيقي"),
        TPMS_OEM("TPMS أصلي"),
        EXTERNAL_SENSOR("حساس خارجي"),
        GPS("GPS"),
        SIMULATION("محاكاة"),
        UNAVAILABLE("غير متاح");

        private final String arabicLabel;

        Source(String arabicLabel) {
            this.arabicLabel = arabicLabel;
        }

        public String label() {
            return arabicLabel;
        }
    }

    public static final long DEFAULT_STALE_AFTER_MS = 3500L;

    public static final class FloatReading {
        public float value = Float.NaN;
        public Source source = Source.UNAVAILABLE;
        public long updatedAtMs = 0L;

        public boolean isAvailable(long nowMs) {
            return !Float.isNaN(value)
                    && source != Source.UNAVAILABLE
                    && updatedAtMs > 0L
                    && nowMs - updatedAtMs <= DEFAULT_STALE_AFTER_MS;
        }
    }

    public static final class IntReading {
        public int value = Integer.MIN_VALUE;
        public Source source = Source.UNAVAILABLE;
        public long updatedAtMs = 0L;

        public boolean isAvailable(long nowMs) {
            return value != Integer.MIN_VALUE
                    && source != Source.UNAVAILABLE
                    && updatedAtMs > 0L
                    && nowMs - updatedAtMs <= DEFAULT_STALE_AFTER_MS;
        }
    }

    public final FloatReading flPsi = new FloatReading();
    public final FloatReading frPsi = new FloatReading();
    public final FloatReading rlPsi = new FloatReading();
    public final FloatReading rrPsi = new FloatReading();

    /** Vehicle/cluster speed when available from the real vehicle source. */
    public final IntReading vehicleSpeedKph = new IntReading();
    /** Raw CAN speed retained separately for calibration and diagnostics. */
    public final IntReading rawCanSpeedKph = new IntReading();
    /** GPS speed retained separately and never silently substituted for CAN. */
    public final IntReading gpsSpeedKph = new IntReading();
    /** Corrected speed is populated only after real calibration is approved. */
    public final IntReading correctedSpeedKph = new IntReading();

    public final IntReading rpm = new IntReading();
    public final IntReading coolantC = new IntReading();
    public final FloatReading voltage = new FloatReading();

    public void set(FloatReading reading, float value, Source source, long nowMs) {
        reading.value = value;
        reading.source = source == null ? Source.UNAVAILABLE : source;
        reading.updatedAtMs = nowMs;
    }

    public void set(IntReading reading, int value, Source source, long nowMs) {
        reading.value = value;
        reading.source = source == null ? Source.UNAVAILABLE : source;
        reading.updatedAtMs = nowMs;
    }

    public void clear(FloatReading reading) {
        reading.value = Float.NaN;
        reading.source = Source.UNAVAILABLE;
        reading.updatedAtMs = 0L;
    }

    public void clear(IntReading reading) {
        reading.value = Integer.MIN_VALUE;
        reading.source = Source.UNAVAILABLE;
        reading.updatedAtMs = 0L;
    }
}
