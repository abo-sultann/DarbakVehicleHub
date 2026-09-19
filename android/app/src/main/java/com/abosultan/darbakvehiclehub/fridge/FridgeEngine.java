package com.abosultan.darbakvehiclehub.fridge;

import android.bluetooth.BluetoothGatt;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class FridgeEngine {
    private final List<FridgeProtocol> protocols = new ArrayList<>();

    public FridgeEngine() {
        protocols.add(new AlpicoolProtocol());
    }

    public List<FridgeProtocol> protocols() { return Collections.unmodifiableList(protocols); }

    public FridgeProtocol detect(String deviceName, BluetoothGatt gatt) {
        for (FridgeProtocol protocol : protocols) {
            if (protocol.matches(deviceName, gatt)) return protocol;
        }
        return null;
    }
}
