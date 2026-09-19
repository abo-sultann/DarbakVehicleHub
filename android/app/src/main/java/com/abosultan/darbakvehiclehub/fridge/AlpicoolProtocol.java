package com.abosultan.darbakvehiclehub.fridge;

import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattService;
import java.util.UUID;

public final class AlpicoolProtocol implements FridgeProtocol {
    public static final UUID SERVICE = UUID.fromString("00001234-0000-1000-8000-00805f9b34fb");
    public static final UUID WRITE = UUID.fromString("00001235-0000-1000-8000-00805f9b34fb");
    public static final UUID NOTIFY = UUID.fromString("00001236-0000-1000-8000-00805f9b34fb");

    @Override public String id() { return "alpicool-1234"; }
    @Override public String displayName() { return "Alpicool / OEM"; }
    @Override public boolean matches(String name, BluetoothGatt gatt) {
        BluetoothGattService s = gatt == null ? null : gatt.getService(SERVICE);
        return s != null && s.getCharacteristic(WRITE) != null && s.getCharacteristic(NOTIFY) != null;
    }
    @Override public FridgeState parse(byte[] payload) { return new FridgeState(); }
    // Command encoding is deliberately disabled until validated against a real unit.
    @Override public byte[] requestStatus() { return null; }
    @Override public byte[] setTargetTemperature(int c) { return null; }
    @Override public byte[] setPower(boolean on) { return null; }
    @Override public byte[] setEco(boolean eco) { return null; }
    @Override public byte[] setBatteryProtection(int level) { return null; }
}
