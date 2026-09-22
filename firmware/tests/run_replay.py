#!/usr/bin/env python3
"""Compile the production decoder, assert exact recorded results, then test the kit."""
from collections import Counter
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "firmware/tests/fixtures"
EXPECTED = {
    "TPMS88_CAPTURE.pulses.txt": {"15B99AA401C05C201C65": 3},
    "TPMS89_CAPTURE.pulses.txt": {"15B99AA401C05C211C66": 4},
    "TPMS_RAW_CAPTURE.pulses.txt": {"15B99AA401C05C201C65": 3},
    "TPMS_20260922.pulses.txt": {
        "15B9C58201005C1E1BAB": 1,
        "15B9C582010153221BA7": 2,
        "15B9C582010153241BA9": 2,
        "15B9C582010153261BAB": 2,
        "15B9C58201005C271BB4": 5,
    },
    "TPMS_LIVE_20260922.pulses.txt": {
        "15B99AA401C05C231C68": 1,
        "15B99AA401C144231C51": 1,
        "15B99AA401C147201C51": 1,
        "15B99AA401C11A241C28": 1,
    },
}

with tempfile.TemporaryDirectory() as directory:
    binary = str(Path(directory) / "replay")
    subprocess.run(["g++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
                    "-I" + str(ROOT / "firmware/include"),
                    str(ROOT / "firmware/tests/replay.cpp"), "-o", binary], check=True)
    for name, expected in EXPECTED.items():
        result = subprocess.run([binary, str(FIXTURES / name)], capture_output=True,
                                text=True, check=True)
        actual = Counter(line.split()[-1] for line in result.stdout.splitlines())
        if actual != expected:
            raise AssertionError(f"{name}: {dict(actual)} != {expected}")
        print(f"{name}: {sum(actual.values())} exact recorded frames, PASS")
    subprocess.run(["python3", str(ROOT / "firmware/tests/test_capture.py")], check=True)
print("All decoder replay and capture tests passed.")
