package com.abosultan.darbakvehiclehub.update;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.provider.Settings;
import androidx.core.content.FileProvider;
import com.abosultan.darbakvehiclehub.BuildConfig;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

public final class UpdateManager {
    private static final String MANIFEST_URL = "https://raw.githubusercontent.com/abo-sultann/DarbakVehicleHub/main/updates/latest.json";
    private final Activity activity;
    public UpdateManager(Activity activity){ this.activity=activity; }

    public void check(){
        final AlertDialog wait=new AlertDialog.Builder(activity).setTitle("تحديث دربك").setMessage("جاري التحقق من آخر نسخة…").setCancelable(true).show();
        final Handler h=new Handler();
        final Runnable timeout=new Runnable(){@Override public void run(){if(wait.isShowing()){wait.dismiss();new AlertDialog.Builder(activity).setTitle("التحديث").setMessage("تعذر الاتصال بخادم التحديث • حاول مرة أخرى").setPositiveButton("إغلاق",null).show();}}};
        h.postDelayed(timeout,6500);
        new Thread(new Runnable(){@Override public void run(){
            String error=null,version=null,url=null,notes=null; int code=0;
            try{
                HttpURLConnection c=(HttpURLConnection)new URL(MANIFEST_URL).openConnection();
                c.setConnectTimeout(5000);c.setReadTimeout(5000);c.setUseCaches(false);c.setRequestProperty("Cache-Control","no-cache");
                int http=c.getResponseCode();if(http<200||http>=300)throw new java.io.IOException("HTTP "+http);
                BufferedReader r=new BufferedReader(new InputStreamReader(c.getInputStream(),"UTF-8"));
                StringBuilder b=new StringBuilder();String line;while((line=r.readLine())!=null)b.append(line);r.close();
                JSONObject j=new JSONObject(b.toString());code=j.getInt("versionCode");version=j.optString("versionName","");url=j.getString("downloadUrl");notes=j.optString("notes","");
            }catch(Exception e){error=e.getClass().getSimpleName();}
            final String fe=error,fv=version,fu=url,fn=notes;final int fc=code;
            activity.runOnUiThread(new Runnable(){@Override public void run(){
                h.removeCallbacks(timeout);if(wait.isShowing())wait.dismiss();
                if(fe!=null){new AlertDialog.Builder(activity).setTitle("التحديث").setMessage("تعذر التحقق الآن • "+fe).setPositiveButton("إغلاق",null).show();return;}
                if(fc<=BuildConfig.VERSION_CODE){new AlertDialog.Builder(activity).setTitle("التحديث").setMessage("أنت على أحدث نسخة • v"+BuildConfig.VERSION_NAME).setPositiveButton("حسنًا",null).show();return;}
                new AlertDialog.Builder(activity).setTitle("تحديث متاح • v"+fv).setMessage(fn.length()==0?"نسخة أحدث متاحة.":fn).setNegativeButton("لاحقًا",null).setPositiveButton("تحديث الآن",(d,w)->downloadAndInstall(fu)).show();
            }});
        }}).start();
    }

    private void downloadAndInstall(final String url){
        final AlertDialog progress=new AlertDialog.Builder(activity).setTitle("تحديث دربك").setMessage("جاري تنزيل التحديث داخل التطبيق…").setCancelable(false).show();
        new Thread(new Runnable(){@Override public void run(){
            String error=null;File apk=null;
            try{
                HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();
                c.setInstanceFollowRedirects(true);c.setConnectTimeout(10000);c.setReadTimeout(30000);
                int http=c.getResponseCode();if(http<200||http>=400)throw new java.io.IOException("HTTP "+http);
                File dir=activity.getExternalCacheDir();if(dir==null)dir=activity.getCacheDir();
                apk=new File(dir,"DarbakVehicleHub-update.apk");
                InputStream in=c.getInputStream();FileOutputStream out=new FileOutputStream(apk);byte[] buf=new byte[8192];int n;
                while((n=in.read(buf))>0)out.write(buf,0,n);out.flush();out.close();in.close();
            }catch(Exception e){error=e.getClass().getSimpleName();}
            final String fe=error;final File fa=apk;
            activity.runOnUiThread(new Runnable(){@Override public void run(){progress.dismiss();if(fe!=null||fa==null){new AlertDialog.Builder(activity).setTitle("التحديث").setMessage("تعذر تنزيل التحديث • "+fe).setPositiveButton("إغلاق",null).show();return;}installApk(fa);}});
        }}).start();
    }

    private void installApk(File apk){
        if(Build.VERSION.SDK_INT>=26&&!activity.getPackageManager().canRequestPackageInstalls()){
            activity.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+activity.getPackageName())));
            return;
        }
        Uri uri=FileProvider.getUriForFile(activity,activity.getPackageName()+".fileprovider",apk);
        Intent i=new Intent(Intent.ACTION_VIEW);i.setDataAndType(uri,"application/vnd.android.package-archive");i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_ACTIVITY_NEW_TASK);activity.startActivity(i);
    }
}
