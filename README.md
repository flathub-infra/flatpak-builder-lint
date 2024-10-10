# flatpak-builder-lint

flatpak-builder-lint is a linter for flatpak-builder manifests, and more widely,
also Flatpak builds. It is primarily developed for Flathub, but can be useful
for other Flatpak repositories.

## Installation

The only supported ways to install and use it are Flatpak and Docker.

### Flatpak

flatpak-builder-lint is part of the `org.flatpak.Builder` flatpak package
available on Flathub. [Set up Flatpak][flatpak_setup] first, then install
`org.flatpak.Builder`:

```bash
flatpak install flathub -y org.flatpak.Builder
flatpak run --command=flatpak-builder-lint org.flatpak.Builder --help

# Run the manifest check
flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest com.foo.bar.json

# Run the repo check
flatpak run --command=flatpak-builder-lint org.flatpak.Builder repo repo
```

The Flatpak package tracks the git commit currently used on the Flathub
infrastructure.

### Docker

The latest build of flatpak-builder-linter can be used with Docker.

```bash
docker run --rm -it ghcr.io/flathub/flatpak-builder-lint:latest --help

# Run the manifest check
docker run -v $(pwd):/mnt --rm -it ghcr.io/flathub/flatpak-builder-lint:latest manifest /mnt/com.foo.bar.json

# Run the repo check
docker run -v $(pwd):/mnt --rm -it ghcr.io/flathub/flatpak-builder-lint:latest repo /mnt/repo
```

You may need to pass `:Z` if your distro is using SELinux like so
`-v $(pwd):/mnt:Z`.

### Local environment

Installing flatpak-builder-lint locally with [Poetry][poetry] or pip is
not recommended unless for development purposes. It depends on patches
that are found in the `org.flatpak.Builder` flatpak package
and on external tools.

## Contributing

The following system dependencies must be installed:

- `libgirepository1.0-dev, gir1.2-ostree-1.0`
- `flatpak-builder` for validating flatpak-builder manifests
- `appstreamcli` from `org.flatpak.Builder` for validating MetaInfo files
```sh
#!/bin/sh

exec flatpak run --branch=stable --command=appstreamcli org.flatpak.Builder ${@}
```
- `desktop-file-validate` to validate desktop files
- `git` to check if a directory is a git repository

Debiab/Ubuntu:

```
# apt install git appstream flatpak-builder libgirepository1.0-dev gir1.2-ostree-1.0 libcairo2-dev desktop-file-utils
```

ArchLinux:

```
# pacman -S --needed git appstream flatpak-builder desktop-file-utils ostree glib2
```

Fedora:

```
# dnf install git appstream flatpak-builder desktop-file-utils ostree-libs glib2-devel cairo-devel
```

Then the project can be installed with:

```bash
git clone https://github.com/flathub/flatpak-builder-lint.git && cd flatpak-builder-lint
poetry install
poetry run flatpak-builder-lint --help
```

After making changes to any dependencies run
`poetry lock --no-update` to regenerate the lockfile and
`poetry install --sync` to synchronise the virtual environment when
chaning code or dependencies.

The virtual enviroment can be listed with `poetry env list` and removed
with `poetry env remove flatpak-builder-lint-xxxxxxxx-py3.xx`.

The following Python dependencies are installed by Poetry and needed to
run `jsonschema^4.19.1, requests^2.32.2, requests-cache^1.2.1, lxml^5.2.2,
sentry-sdk^2.8.0, PyGObject^3.48.2`. Additionally `poetry-core>=1.0.0`
is necessary to build.

[Ruff](https://docs.astral.sh/ruff/installation/) is used to lint and
format code. [MyPy](https://mypy.readthedocs.io/en/stable/getting_started.html)
is used to check Python types. To run them:

```sh
# Formatting
poetry run ruff format .

# Linting
poetry run ruff check .

# Auto fix some lint errrors
poetry run ruff check --fix .

# Check python types
poetry run mypy .
```

A pre-commit hook is provided to automate the formatting and linting:

```
poetry run pre-commit install
poetry run pre-commit run --all-files

# Uninstall hooks
poetry run pre-commit uninstall
```

[Pytest](https://docs.pytest.org/en/stable/getting-started.html) is used
to run tests:

```sh
poetry run pytest -v tests
```

An additional Flat manager test can be run when modifying code relying
on the flatmanager check. The check is meant to be run on CI and not
locally. If it is being run locally it must be run from the root of the
git repository using

```sh
./tests/flatmanager.sh

# Avoid repeated rebuilds
NO_CLEAN_UP=1 ./tests/flatmanager.sh
```

## Usage

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
