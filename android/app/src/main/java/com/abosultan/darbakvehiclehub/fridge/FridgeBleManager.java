package com.abosultan.darbakvehiclehub.fridge;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.*;
import android.bluetooth.le.*;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Handler;
import android.os.ParcelUuid;
import java.util.*;

public final class FridgeBleManager {
 public interface Listener { void onStatus(String s); void onDevice(String n); void onGattProfile(String p); void onProtocol(String p); }
 private static final long SCAN_MS=15000L;
 private static final String ICECO_PREFIX="24:35:CC";
 private final Activity activity; private final Listener listener; private final Handler handler=new Handler(); private final FridgeEngine engine=new FridgeEngine();
 private BluetoothLeScanner scanner; private BluetoothGatt gatt; private boolean scanning; private ScanResult bestCandidate;

 public FridgeBleManager(Activity a,Listener l){activity=a;listener=l;}
 public boolean hasLocationPermission(){return activity.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED;}
 public int bluetoothState(){
  BluetoothManager bm=(BluetoothManager)activity.getSystemService(Context.BLUETOOTH_SERVICE);
  BluetoothAdapter a=bm==null?null:bm.getAdapter();
  if(a==null)return 0;
  return a.isEnabled()?2:1;
 }
 public void requestEnableBluetooth(){
  BluetoothManager bm=(BluetoothManager)activity.getSystemService(Context.BLUETOOTH_SERVICE);
  BluetoothAdapter a=bm==null?null:bm.getAdapter();
  if(a!=null&&!a.isEnabled())activity.startActivityForResult(new android.content.Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE),702);
 }

 public void startScan(){
  if(!hasLocationPermission()){listener.onStatus("يحتاج إذن الموقع لمسح BLE على Android 7.1");return;}
  BluetoothManager bm=(BluetoothManager)activity.getSystemService(Context.BLUETOOTH_SERVICE); BluetoothAdapter a=bm==null?null:bm.getAdapter();
  if(a==null){listener.onStatus("Bluetooth غير مدعوم من النظام");return;}
  if(!a.isEnabled()){listener.onStatus("Bluetooth متوقف • اضغط لتشغيله");return;}
  scanner=a.getBluetoothLeScanner(); if(scanner==null){listener.onStatus("BLE Scanner غير متاح");return;}
  stopScan(); bestCandidate=null; scanning=true; listener.onStatus("جاري البحث عن الثلاجة…");
  scanner.startScan(Collections.<ScanFilter>emptyList(),new ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(),scanCallback);
  handler.postDelayed(new Runnable(){@Override public void run(){if(scanning){ScanResult c=bestCandidate;stopScan();if(c!=null)connect(c,"مرشح BLE الأقرب");else listener.onStatus("انتهى البحث • لم يظهر جهاز BLE مناسب");}}},SCAN_MS);
 }

 public void stopScan(){scanning=false;handler.removeCallbacksAndMessages(null);if(scanner!=null)try{scanner.stopScan(scanCallback);}catch(Exception ignored){}}
 public void close(){stopScan();if(gatt!=null){gatt.disconnect();gatt.close();gatt=null;}}

 private final ScanCallback scanCallback=new ScanCallback(){
  @Override public void onScanResult(int t,ScanResult r){
   BluetoothDevice d=r.getDevice(); if(d==null)return;
   String n=d.getName(); String addr=d.getAddress(); ScanRecord rec=r.getScanRecord();
   if(isStrongMatch(n,addr,rec)){stopScan();connect(r,"تطابق ثلاجة");return;}
   if(bestCandidate==null||r.getRssi()>bestCandidate.getRssi())bestCandidate=r;
  }
  @Override public void onScanFailed(int code){stopScan();listener.onStatus("فشل مسح BLE • code="+code);}
 };

 private void connect(ScanResult r,String reason){
  BluetoothDevice d=r.getDevice(); String n=d.getName(); String label=(n==null||n.trim().isEmpty())?"BLE device":n;
  listener.onDevice(label+" • "+d.getAddress()+" • RSSI "+r.getRssi());
  listener.onStatus(reason+" • فحص GATT فقط");
  if(gatt!=null){try{gatt.close();}catch(Exception ignored){}}
  gatt=d.connectGatt(activity,false,gattCallback);
 }

 private final BluetoothGattCallback gattCallback=new BluetoothGattCallback(){
  @Override public void onConnectionStateChange(BluetoothGatt g,int s,int ns){
   if(ns==BluetoothProfile.STATE_CONNECTED){listener.onStatus("متصل • اكتشاف GATT");g.discoverServices();}
   else if(ns==BluetoothProfile.STATE_DISCONNECTED)listener.onStatus("غير متصل • status="+s);
  }
  @Override public void onServicesDiscovered(BluetoothGatt g,int s){
   listener.onGattProfile(describe(g));
   FridgeProtocol p=engine.detect(g.getDevice().getName(),g);
   listener.onProtocol(p==null?"غير معروف • قراءة فقط":p.displayName());
   listener.onStatus(p==null?"متصل • GATT محفوظ للتشخيص":"متصل • تم التعرف على البروتوكول");
  }
 };

 private static boolean isStrongMatch(String n,String addr,ScanRecord rec){
  if(addr!=null&&addr.toUpperCase(Locale.US).startsWith(ICECO_PREFIX))return true;
  if(n!=null){String x=n.toLowerCase(Locale.US);if(x.contains("refriger")||x.contains("fridge")||x.contains("iceco")||x.contains("alpicool")||x.contains("freezer"))return true;}
  if(rec!=null&&rec.getServiceUuids()!=null)for(ParcelUuid u:rec.getServiceUuids())if(AlpicoolProtocol.SERVICE.equals(u.getUuid()))return true;
  return false;
 }

 private static String describe(BluetoothGatt g){
  StringBuilder b=new StringBuilder();
  for(BluetoothGattService s:g.getServices()){
   if(b.length()>0)b.append("
");
   b.append("S ").append(s.getUuid());
   for(BluetoothGattCharacteristic c:s.getCharacteristics()){
    b.append("
  C ").append(c.getUuid()).append(" [").append(properties(c.getProperties())).append("]");
   }
  }
  return b.length()==0?"لا توجد خدمات":b.toString();
 }
 private static String properties(int p){
  StringBuilder b=new StringBuilder();
  if((p&BluetoothGattCharacteristic.PROPERTY_READ)!=0)b.append("R");
  if((p&BluetoothGattCharacteristic.PROPERTY_WRITE)!=0)b.append("W");
  if((p&BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE)!=0)b.append("w");
  if((p&BluetoothGattCharacteristic.PROPERTY_NOTIFY)!=0)b.append("N");
  if((p&BluetoothGattCharacteristic.PROPERTY_INDICATE)!=0)b.append("I");
  return b.length()==0?"-":b.toString();
 }
}
