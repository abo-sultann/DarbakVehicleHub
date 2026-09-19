package com.abosultan.darbakvehiclehub.fridge;

import android.bluetooth.BluetoothGatt;

public interface FridgeProtocol {
    String id();
    String displayName();
    boolean matches(String deviceName, BluetoothGatt gatt);
    FridgeState parse(byte[] payload);
    byte[] requestStatus();
    byte[] setTargetTemperature(int celsius);
    byte[] setPower(boolean on);
    byte[] setEco(boolean eco);
    byte[] setBatteryProtection(int level);
}
