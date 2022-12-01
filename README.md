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

Installing
-------

You can install flatpak-builder-lint directly from githHub by running this command
```shell
$ pip install -U git+https://github.com/flathub/flatpak-builder-lint.git
```

You can run it anywhere with
```shell
$ flatpak-builder-lint MANIFEST
```

Flatpak
-------

This tool is part of the flatpak-builder flatpak
`org.flatpak.Builder`. After installing you can run the linter from
the command-line:

```shell
flatpak run --command=flatpak-builder-lint org.flatpak.Builder MANIFEST
```

(`MANIFEST` is the path to the manifest to lint, same as above).
