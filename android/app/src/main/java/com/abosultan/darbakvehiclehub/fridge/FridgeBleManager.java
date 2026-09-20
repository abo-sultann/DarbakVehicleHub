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
 private static final long CONNECT_TIMEOUT_MS=12000L;
 private static final long DISCOVER_DELAY_MS=600L;
 private static final long DISCOVER_TIMEOUT_MS=10000L;
 private static final String ICECO_PREFIX="24:35:CC";
 private final Activity activity; private final Listener listener; private final Handler handler=new Handler(); private final FridgeEngine engine=new FridgeEngine();
 private BluetoothLeScanner scanner; private BluetoothGatt gatt; private boolean scanning; private ScanResult bestCandidate;
 private final Runnable scanTimeout=new Runnable(){@Override public void run(){if(!scanning)return;ScanResult c=bestCandidate;stopScanOnly();if(c!=null&&isStrongMatch(c.getDevice().getName(),c.getDevice().getAddress(),c.getScanRecord()))connect(c,"تطابق ثلاجة");else listener.onStatus("انتهى البحث • لم تظهر ثلاجة معروفة");}};
 private final Runnable connectTimeout=new Runnable(){@Override public void run(){listener.onStatus("انتهت مهلة اتصال BLE • أعد البحث");closeGatt();}};
 private final Runnable discoverTimeout=new Runnable(){@Override public void run(){listener.onStatus("تعذر اكتشاف خدمات GATT • أعد البحث");listener.onGattProfile("لم تصل خدمات GATT خلال المهلة");closeGatt();}};

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
  if(a==null){listener.onStatus("Bluetooth غير مدعوم من النظام");return;}
  if(a.isEnabled()){listener.onStatus("Bluetooth يعمل • بدء البحث");startScan();return;}
  listener.onStatus("بانتظار تشغيل Bluetooth…");
  try{activity.startActivityForResult(new android.content.Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE),702);}
  catch(Exception e){listener.onStatus("تعذر فتح طلب تشغيل Bluetooth");}
 }

 public void startScan(){
  if(!hasLocationPermission()){listener.onStatus("يحتاج إذن الموقع لمسح BLE على Android 7.1");return;}
  BluetoothManager bm=(BluetoothManager)activity.getSystemService(Context.BLUETOOTH_SERVICE); BluetoothAdapter a=bm==null?null:bm.getAdapter();
  if(a==null){listener.onStatus("Bluetooth غير مدعوم من النظام");return;}
  if(!a.isEnabled()){listener.onStatus("Bluetooth متوقف • اضغط لتشغيله");return;}
  scanner=a.getBluetoothLeScanner(); if(scanner==null){listener.onStatus("BLE Scanner غير متاح");return;}
  stopScanOnly(); closeGatt(); bestCandidate=null; scanning=true; listener.onStatus("1/4 • جاري البحث عن الثلاجة…");
  try{
   scanner.startScan(Collections.<ScanFilter>emptyList(),new ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(),scanCallback);
   handler.postDelayed(scanTimeout,SCAN_MS);
  }catch(Exception e){scanning=false;listener.onStatus("تعذر بدء مسح BLE");}
 }

 private void stopScanOnly(){
  scanning=false;handler.removeCallbacks(scanTimeout);
  if(scanner!=null)try{scanner.stopScan(scanCallback);}catch(Exception ignored){}
 }
 public void stopScan(){stopScanOnly();}
 public void close(){handler.removeCallbacksAndMessages(null);stopScanOnly();closeGatt();}
 private void closeGatt(){handler.removeCallbacks(connectTimeout);handler.removeCallbacks(discoverTimeout);if(gatt!=null){try{gatt.disconnect();}catch(Exception ignored){}try{gatt.close();}catch(Exception ignored){}gatt=null;}}

 private final ScanCallback scanCallback=new ScanCallback(){
  @Override public void onScanResult(int t,ScanResult r){
   BluetoothDevice d=r.getDevice(); if(d==null)return;
   String n=d.getName(); String addr=d.getAddress(); ScanRecord rec=r.getScanRecord();
   if(isStrongMatch(n,addr,rec)){stopScanOnly();connect(r,"2/4 • تم العثور على الثلاجة");return;}
   if(bestCandidate==null||r.getRssi()>bestCandidate.getRssi())bestCandidate=r;
  }
  @Override public void onScanFailed(int code){stopScanOnly();listener.onStatus("فشل مسح BLE • scanCode="+code);}
 };

 private void connect(ScanResult r,String reason){
  BluetoothDevice d=r.getDevice(); String n=d.getName(); String label=(n==null||n.trim().isEmpty())?"BLE device":n;
  listener.onDevice(label+" • "+d.getAddress()+" • RSSI "+r.getRssi());
  listener.onStatus(reason+" • جاري الاتصال…");
  closeGatt();
  try{
   gatt=d.connectGatt(activity,false,gattCallback);
   handler.postDelayed(connectTimeout,CONNECT_TIMEOUT_MS);
  }catch(Exception e){listener.onStatus("تعذر بدء اتصال GATT");}
 }

 private final BluetoothGattCallback gattCallback=new BluetoothGattCallback(){
  @Override public void onConnectionStateChange(final BluetoothGatt g,int s,int ns){
   if(ns==BluetoothProfile.STATE_CONNECTED&&s==BluetoothGatt.GATT_SUCCESS){
    handler.removeCallbacks(connectTimeout);
    listener.onStatus("3/4 • متصل • تجهيز اكتشاف GATT…");
    handler.postDelayed(new Runnable(){@Override public void run(){
     if(gatt!=g)return;
     boolean started=false;try{started=g.discoverServices();}catch(Exception ignored){}
     if(started){listener.onStatus("3/4 • متصل • اكتشاف خدمات GATT…");handler.postDelayed(discoverTimeout,DISCOVER_TIMEOUT_MS);}
     else{listener.onStatus("فشل بدء اكتشاف GATT");closeGatt();}
    }},DISCOVER_DELAY_MS);
   }else if(ns==BluetoothProfile.STATE_DISCONNECTED){
    handler.removeCallbacks(connectTimeout);handler.removeCallbacks(discoverTimeout);
    listener.onStatus("انقطع BLE • gattStatus="+s);
   }else if(s!=BluetoothGatt.GATT_SUCCESS){
    handler.removeCallbacks(connectTimeout);handler.removeCallbacks(discoverTimeout);
    listener.onStatus("خطأ اتصال BLE • gattStatus="+s);
    closeGatt();
   }
  }
  @Override public void onServicesDiscovered(BluetoothGatt g,int s){
   handler.removeCallbacks(discoverTimeout);
   if(s!=BluetoothGatt.GATT_SUCCESS){listener.onStatus("فشل اكتشاف GATT • gattStatus="+s);listener.onGattProfile("اكتشاف الخدمات فشل • status="+s);return;}
   String profile=describe(g);listener.onGattProfile(profile);
   FridgeProtocol p=engine.detect(g.getDevice().getName(),g);
   listener.onProtocol(p==null?"غير معروف • قراءة فقط":p.displayName());
   listener.onStatus(p==null?"4/4 • GATT مكتشف • البروتوكول غير معروف":"4/4 • تم التعرف على البروتوكول");
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
  for(BluetoothGattService service:g.getServices()){
   if(b.length()>0)b.append((char)10);
   b.append("S ").append(service.getUuid());
   for(BluetoothGattCharacteristic characteristic:service.getCharacteristics()){
    b.append((char)10).append("  C ").append(characteristic.getUuid()).append(" [").append(properties(characteristic.getProperties())).append("]");
   }
  }
  return b.length()==0?"لا توجد خدمات GATT":b.toString();
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
