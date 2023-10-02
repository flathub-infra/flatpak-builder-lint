import os
import subprocess


def validate(path: str) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError("AppStream file not found")
    cmd = subprocess.run(
        ["appstream-util", "validate", path],
        capture_output=True,
    )

    ret = {
        "stdout": cmd.stdout.decode("utf-8"),
        "stderr": cmd.stderr.decode("utf-8"),
        "returncode": cmd.returncode,
    }

    return ret
