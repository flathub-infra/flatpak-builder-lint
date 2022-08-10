import json
import subprocess
import typing

# json-glib supports non-standard syntax like // comments. Bail out and
# delegate parsing to flatpak-builder.
def show_manifest(filename: str) -> typing.Dict:
    ret = subprocess.run(
        ["flatpak-builder", "--show-manifest", filename], capture_output=True
    )

    if ret.returncode != 0:
        raise Exception(ret.stderr.decode("utf-8"))

    manifest = ret.stdout.decode("utf-8")
    return json.loads(manifest)
