package com.abosultan.darbakvehiclehub.fridge;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.*;
import android.bluetooth.le.*;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Handler;
import java.util.*;

public final class FridgeBleManager {
 public interface Listener { void onStatus(String s); void onDevice(String n); void onGattProfile(String p); void onProtocol(String p); }
 private static final long SCAN_MS=12000L;
 private final Activity activity; private final Listener listener; private final Handler handler=new Handler(); private final FridgeEngine engine=new FridgeEngine();
 private BluetoothLeScanner scanner; private BluetoothGatt gatt; private boolean scanning;
 public FridgeBleManager(Activity a,Listener l){activity=a;listener=l;}
 public boolean hasLocationPermission(){return activity.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED;}
 public void startScan(){
  if(!hasLocationPermission()){listener.onStatus("يحتاج إذن الموقع لمسح BLE على Android 7.1");return;}
  BluetoothManager bm=(BluetoothManager)activity.getSystemService(Context.BLUETOOTH_SERVICE); BluetoothAdapter a=bm==null?null:bm.getAdapter();
  if(a==null||!a.isEnabled()){listener.onStatus("Bluetooth غير متاح أو متوقف");return;}
  scanner=a.getBluetoothLeScanner(); if(scanner==null){listener.onStatus("BLE Scanner غير متاح");return;}
  stopScan(); scanning=true; listener.onStatus("جاري البحث عن الثلاجة…"); scanner.startScan(scanCallback);
  handler.postDelayed(new Runnable(){@Override public void run(){if(scanning){stopScan();listener.onStatus("انتهى البحث • لم يتم اعتماد جهاز بعد");}}},SCAN_MS);
 }
 public void stopScan(){scanning=false;handler.removeCallbacksAndMessages(null);if(scanner!=null)try{scanner.stopScan(scanCallback);}catch(Exception ignored){}}
 public void close(){stopScan();if(gatt!=null){gatt.close();gatt=null;}}
 private final ScanCallback scanCallback=new ScanCallback(){@Override public void onScanResult(int t,ScanResult r){BluetoothDevice d=r.getDevice();String n=d==null?null:d.getName();if(!looksLikeFridge(n))return;stopScan();listener.onDevice(n==null?"BLE device":n);listener.onStatus("تم العثور • فحص الخدمات فقط");gatt=d.connectGatt(activity,false,gattCallback);}};
 private final BluetoothGattCallback gattCallback=new BluetoothGattCallback(){
  @Override public void onConnectionStateChange(BluetoothGatt g,int s,int ns){if(ns==BluetoothProfile.STATE_CONNECTED){listener.onStatus("متصل • اكتشاف GATT");g.discoverServices();}else if(ns==BluetoothProfile.STATE_DISCONNECTED)listener.onStatus("غير متصل");}
  @Override public void onServicesDiscovered(BluetoothGatt g,int s){listener.onGattProfile(describe(g));FridgeProtocol p=engine.detect(g.getDevice().getName(),g);listener.onProtocol(p==null?"غير معروف • قراءة فقط":p.displayName());listener.onStatus(p==null?"متصل • البروتوكول غير معروف":"متصل • تم التعرف على البروتوكول");}
 };
 private static boolean looksLikeFridge(String n){if(n==null)return false;n=n.toLowerCase(Locale.US);return n.contains("refriger")||n.contains("fridge")||n.contains("iceco")||n.contains("alpicool")||n.contains("freezer");}
 private static String describe(BluetoothGatt g){StringBuilder b=new StringBuilder();for(BluetoothGattService s:g.getServices()){if(b.length()>0)b.append("\n");b.append(s.getUuid());}return b.length()==0?"لا توجد خدمات":b.toString();}
}