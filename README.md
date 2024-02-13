# flatpak-builder-lint

flatpak-builder-lint is a linter for flatpak-builder manifests, and more widely,
also Flatpak builds. It is primarily developed for Flathub, but can be useful
for other Flatpak repositories.

## Installation

### Docker

The latest build of flatpak-builder-linter can be used with Docker.

```
docker run --rm -it ghcr.io/flathub/flatpak-builder-lint:latest
```

You may need to pass the local data using `--volume` to check the chosen file
or repo.

### Flatpak

flatpak-builder-lint is part of the `org.flatpak.Builder` flatpak package
available on Flathub. [Set up Flatpak][flatpak_setup] first, then install
`org.flatpak.Builder`:

```bash
flatpak install flathub -y org.flatpak.Builder
flatpak run --command=flatpak-builder-lint org.flatpak.Builder --help
```

The flatpak package tracks the git commit currently used on the Flathub
infrastructure.

### Local environment

Due to soft requirements for versions of external tools, flatpak-builder-lint
locally is not recommended. If you know what you're doing, it can be installed
using [Poetry][poetry].

```bash
git clone https://github.com/flathub/flatpak-builder-lint
cd flatpak-builder-lint
poetry install 
poetry run flatpak-builder-lint --help
```
Additional tools are required by subcommands and checks:

- `flatpak-builder` for validating flatpak-builder manifests,
- `ostree` for validating ostree repositories containing builds,
- `appstreamcli` from `appstream` for validating AppStream.

### Usage

```
usage: flatpak-builder-lint [-h] [--json] [--version] [--exceptions] [--appid APPID] {builddir,repo,manifest} path

A linter for Flatpak builds and flatpak-builder manifests

positional arguments:
  {builddir,repo,manifest}
                        type of artifact to lint
  path                  path to flatpak-builder manifest or Flatpak build directory

options:
  -h, --help            show this help message and exit
  --json                output in JSON format
  --version             show program's version number and exit
  --exceptions          skip allowed warnings or errors
  --appid APPID         override app ID
```

[poetry]: https://python-poetry.org/docs/#installation
[flatpak_setup]: https://flathub.org/setup
