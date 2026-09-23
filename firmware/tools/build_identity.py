Import("env")
import os
import subprocess

revision = os.environ.get("TPMS_BUILD_COMMIT")
if not revision:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
    raise ValueError("Expected a full Git commit SHA for the firmware identity")
env.Append(CPPDEFINES=[("TPMS_BUILD_SHA", '\\\"' + revision[:12] + '\\\"')])
