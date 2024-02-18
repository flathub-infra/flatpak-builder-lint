import collections
import json
import sys

def check_duplicates(pairs):
    count = collections.Counter(i for i,j in pairs)
    duplicates = ", ".join(i for i,j in count.items() if j>1)

    if len(duplicates) != 0:
        print("Duplicate keys found: {}".format(duplicates))
        sys.exit(1)

def validate(pairs):
    check_duplicates(pairs)
    return dict(pairs)

with open("flatpak_builder_lint/staticfiles/exceptions.json", "r") as file:
    try:
        obj = json.load(file, object_pairs_hook=validate)
    except ValueError as e:
        print("Invalid json: %s" % e)
        sys.exit(1)
