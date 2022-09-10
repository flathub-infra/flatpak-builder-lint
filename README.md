flatpak-builder-lint
====================

This is a linter for flatpak manifests.

Requirements:

- poetry
- python 3.8
- flatpak-builder


Running
-------

First you need to install the dependencies

```shell
$ poetry install
```

To run
```shell
$ poetry run flatpak-builder-lint MANIFEST
```

where MANIFEST is the manifest to check.
