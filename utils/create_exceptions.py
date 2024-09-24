import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument(
    "--appidfile",
    nargs=1,
    type=str,
    required=True,
    help="Input filename with 1 appid per line or a single appid",
)
parser.add_argument(
    "--exception",
    action="extend",
    nargs="*",
    type=str,
    required=True,
    help="Input error code to create exception. Can be used multiple times",
)
parser.add_argument("--reason", nargs=1, type=str, help="Input optional reason string")
args = parser.parse_args()

if not args.reason:
    reason = "Predates the linter rule"
else:
    reason = args.reason[0]

excps = args.exception
appids = set()

try:
    with open(args.appidfile[0]) as f:
        for line in f:
            appids.add(line.strip("\n"))
except FileNotFoundError:
    appids.add(args.appidfile[0])
    pass

data = {}
for app in appids:
    excps_tmp = {}
    for ex in excps:
        excps_tmp.update({f"{ex}": f"{reason}"})
    data[app] = excps_tmp

print(json.dumps(data, sort_keys=True, indent=4))  # noqa: T201
