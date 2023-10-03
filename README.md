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
$ poetry run flatpak-builder-lint KIND MANIFEST
```

where KIND is the kind of manifest to check (e.g. `manifest`, `repo` or `builddir`) and MANIFEST is the path to the manifest to check.

Flatpak
-------

This tool is part of the flatpak-builder flatpak
`org.flatpak.Builder`. After installing you can run the linter from
the command-line:

```shell
flatpak run --command=flatpak-builder-lint org.flatpak.Builder MANIFEST
```

(`MANIFEST` is the path to the manifest to lint, same as above).
