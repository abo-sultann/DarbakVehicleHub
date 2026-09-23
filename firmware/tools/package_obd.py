#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
root=Path(__file__).resolve().parents[2]
out=root/'dist-obd'
out.mkdir(exist_ok=True)
files={root/'firmware/.pio/build/esp32_obd_tpms/firmware.bin':'DarbakVehicleHub-ESP32-OBD-TPMS.bin',
       root/'firmware/tools/obd_tpms_capture.py':'obd_tpms_capture.py',
       root/'firmware/tools/Test-OBD-TPMS.ps1':'Test-OBD-TPMS.ps1',
       root/'docs/OBD_TPMS_TEST.md':'READ_ME.md'}
for src,name in files.items(): shutil.copyfile(src,out/name)
commit=os.environ.get('TPMS_BUILD_COMMIT') or subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
manifest={'commit':commit,'mode':'obd_tpms','mapping_verified':False,
          'flash_offset':'0x10000','flash_scope':'application_only_existing_esp32_installation',
          'tx_pin':21,'rx_pin':22,'bitrate':500000,
          'sha256':{name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in files.values()}}
(out/'manifest-obd.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('Packaged OBD-only TPMS test',commit)
