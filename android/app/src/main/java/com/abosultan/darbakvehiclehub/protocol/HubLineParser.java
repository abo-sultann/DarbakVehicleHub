package com.abosultan.darbakvehiclehub.protocol;

import org.json.JSONException;
import org.json.JSONObject;

public final class HubLineParser {
    public static JSONObject parse(String line) throws JSONException {
        JSONObject obj = new JSONObject(line);
        if (obj.optInt("v", -1) != 1) {
            throw new JSONException("Unsupported protocol version");
        }
        return obj;
    }

    private HubLineParser() {}
}
