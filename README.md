# flatpak-builder-lint

flatpak-builder-lint is a linter for flatpak-builder manifests, and more widely,
also Flatpak builds. It is primarily developed for Flathub, but can be useful
for other Flatpak repositories.

## Installation

The only supported ways to install and use it are Docker and Flatpak.

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

Installing flatpak-builder-lint locally with [Poetry][poetry] or pip is
not recommended unless for development purposes. It depends on patches
that are found in the `org.flatpak.Builder` flatpak package
and on external tools.

```bash
git clone https://github.com/flathub/flatpak-builder-lint
cd flatpak-builder-lint
poetry install
poetry run flatpak-builder-lint --help
```
Additional tools are required by subcommands and checks:

- `flatpak-builder` for validating flatpak-builder manifests
- `ostree` for validating ostree repositories containing builds
- `appstreamcli` from `org.flatpak.Builder` for validating MetaInfo files
- `desktop-file-validate` to validate desktop files
- `git` to fetch remote references, used for validating appids using
  code hosting prefixes

### Usage

```
usage: flatpak-builder-lint [-h] [--version] [--exceptions] [--appid APPID] [--cwd] [--ref REF] {builddir,repo,manifest,appstream} path

A linter for Flatpak builds and flatpak-builder manifests

positional arguments:
  {builddir,repo,manifest,appstream}
                        type of artifact to lint
  path                  path to artifact

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --exceptions          skip allowed warnings or errors
  --appid APPID         override app ID
  --cwd                 override the path parameter with current working directory
  --ref REF             override the primary ref detection

If you consider the detected issues incorrect, please report it here: https://github.com/flathub/flatpak-builder-lint
```

[poetry]: https://python-poetry.org/docs/#installation
[flatpak_setup]: https://flathub.org/setup

## Documentation

A list of errors and warnings and their explanations are available in the
[Flatpak builder lint page](https://docs.flathub.org/docs/for-app-authors/linter).
