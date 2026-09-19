package com.abosultan.darbakvehiclehub.fridge;

public final class FridgeState {
    public boolean connected;
    public String deviceName = "غير معروف";
    public String protocol = "غير معروف";
    public Integer currentC;
    public Integer targetC;
    public Float inputVoltage;
    public Boolean powerOn;
    public Boolean eco;
    public Integer batteryProtection;
    public String error;

    public void clearLiveValues() {
        currentC = null; targetC = null; inputVoltage = null;
        powerOn = null; eco = null; batteryProtection = null; error = null;
    }
}
