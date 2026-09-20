package com.abosultan.darbakvehiclehub.update;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Handler;
import com.abosultan.darbakvehiclehub.BuildConfig;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

public final class UpdateManager {
    private static final String MANIFEST_URL = "https://raw.githubusercontent.com/abo-sultann/DarbakVehicleHub/main/updates/latest.json";
    private final Activity activity;
    public UpdateManager(Activity activity){ this.activity=activity; }

    public void check(){
        final AlertDialog wait = new AlertDialog.Builder(activity)
                .setTitle("تحديث دربك")
                .setMessage("جاري التحقق من آخر نسخة…")
                .setCancelable(true).show();
        final Handler timeoutHandler=new Handler();
        final Runnable timeout=new Runnable(){@Override public void run(){if(wait.isShowing()){wait.dismiss();new AlertDialog.Builder(activity).setTitle("التحديث").setMessage("تعذر الاتصال بخادم التحديث • حاول مرة أخرى").setPositiveButton("إغلاق",null).show();}}};
        timeoutHandler.postDelayed(timeout,6500);
        new Thread(new Runnable(){ @Override public void run(){
            String error=null, version=null, url=null, notes=null; int code=0;
            try{
                HttpURLConnection c=(HttpURLConnection)new URL(MANIFEST_URL).openConnection();
                c.setConnectTimeout(5000); c.setReadTimeout(5000); c.setUseCaches(false); c.setRequestProperty("Cache-Control","no-cache");
                int http=c.getResponseCode(); if(http<200||http>=300) throw new java.io.IOException("HTTP "+http);
                BufferedReader r=new BufferedReader(new InputStreamReader(c.getInputStream(),"UTF-8"));
                StringBuilder b=new StringBuilder(); String line; while((line=r.readLine())!=null)b.append(line); r.close();
                JSONObject j=new JSONObject(b.toString());
                code=j.getInt("versionCode"); version=j.optString("versionName",""); url=j.getString("downloadUrl"); notes=j.optString("notes","");
            }catch(Exception e){error=e.getClass().getSimpleName();}
            final String fe=error,fv=version,fu=url,fn=notes; final int fc=code;
            activity.runOnUiThread(new Runnable(){@Override public void run(){
                timeoutHandler.removeCallbacks(timeout);
                if(wait.isShowing())wait.dismiss();
                if(fe!=null){new AlertDialog.Builder(activity).setTitle("التحديث").setMessage("تعذر التحقق الآن • "+fe).setPositiveButton("إغلاق",null).show();return;}
                if(fc<=BuildConfig.VERSION_CODE){new AlertDialog.Builder(activity).setTitle("التحديث").setMessage("أنت على أحدث نسخة • v"+BuildConfig.VERSION_NAME).setPositiveButton("حسنًا",null).show();return;}
                new AlertDialog.Builder(activity).setTitle("تحديث متاح • v"+fv)
                    .setMessage(fn.length()==0?"نسخة أحدث متاحة.":fn)
                    .setNegativeButton("لاحقًا",null)
                    .setPositiveButton("تحديث الآن", (d,w)->downloadAndInstall(fu))
                    .show();
            }});
        }}).start();
    }
}
