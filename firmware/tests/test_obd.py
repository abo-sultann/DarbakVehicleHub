import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import json
import zipfile
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('capture', ROOT/'firmware/tools/obd_tpms_capture.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)

class ObdTests(unittest.TestCase):
    def test_production_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = str(Path(tmp)/'obd')
            subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror',
                            '-I'+str(ROOT/'firmware/include'),
                            str(ROOT/'firmware/tests/obd_transport.cpp'),'-o',binary],check=True)
            subprocess.run([binary],check=True)

    def test_recorded_reply_no_invented_measurements(self):
        for pid, data, expected in [(0x16,'61165455535300',[84,85,83,83,0]),
                                     (0x30,'6130BBBDBEBD00',[187,189,190,189,0])]:
            r=capture.classify({'type':'obd_payload','request_pid':pid,'payload_hex':data})
            self.assertEqual(r['raw_slots'],expected)
            self.assertFalse(r['mapping_verified'])
            self.assertIsNone(r['pressure_psi'])
            self.assertIsNone(r['temperature_c'])
            self.assertIsNone(r['sensor_id'])

    def test_reject_unexpected_and_negative(self):
        for data in ('613000', '61165455535300','not hex'):
            r=capture.classify({'type':'obd_payload','request_pid':0x30,'payload_hex':data})
            self.assertNotIn('raw_slots',r)
        r=capture.classify({'type':'obd_payload','request_pid':0x30,'payload_hex':'7F2112'})
        self.assertEqual(r['nrc'],0x12)
        self.assertEqual(r['status'],'negative_response')

    def test_session_saves_on_firmware_stop(self):
        # Simulate no CAN on the bench: START is refused and the archive survives.
        import serial
        class Clock:
            n=0
            def now(self):
                self.n += 0.2
                return self.n
        class Port:
            is_open=False
            writes=[]
            def open(self): self.is_open=True
            def close(self): self.is_open=False
            def flush(self): pass
            def write(self, data): self.writes.append(data)
            def readline(self):
                stopped=b'START\n' in self.writes
                return json.dumps({'type':'status','mode':'obd_tpms','build':'a'*12,
                                   'active':False,'stopped':stopped}).encode()+b'\n'
        port=Port()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(capture,'verify',return_value={'commit':'a'*40}), \
                 patch.object(capture,'choose_port',return_value='COM3'), \
                 patch.object(capture.subprocess,'run'), \
                 patch.object(capture.time,'monotonic',side_effect=Clock().now), \
                 patch.object(serial,'Serial',return_value=port):
                rc=capture.run(SimpleNamespace(port=None,output=Path(tmp)))
            self.assertEqual(rc,1)
            self.assertIn(b'STOP\n',port.writes)
            self.assertFalse(port.is_open)
            archive=list(Path(tmp).glob('*.zip'))
            self.assertEqual(len(archive),1)
            with zipfile.ZipFile(archive[0]) as z:
                summary=json.loads(z.read('summary.json'))
                self.assertFalse(summary['started'])
                self.assertIsNone(summary['pressure_psi'])
                self.assertIn('session.jsonl',z.namelist())

if __name__=='__main__': unittest.main()
