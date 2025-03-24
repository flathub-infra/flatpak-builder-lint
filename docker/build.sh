#!/usr/bin/env bash

set -euo pipefail

TOP_DIR="$(pwd)"

checkcmd() {
    if ! command -v "$1" > /dev/null 2>&1; then
        echo "$1 not found. Please install it from your distribution."
        exit 1
    fi
}

checkcmd "python3"
checkcmd "git"
checkcmd "flatpak"
checkcmd "flatpak-builder"
checkcmd "docker"

flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --or-update --user -y flathub org.flatpak.Builder

cd "$TOP_DIR"/docker
rm -rf org.flatpak.Builder
git clone --depth=1 --branch master --recursive --single-branch https://github.com/flathub/org.flatpak.Builder.git
cp -vf flatpak-builder-lint-deps.json org.flatpak.Builder/
python3 rewrite-manifest.py
cd org.flatpak.Builder

flatpak run org.flatpak.Builder --user --force-clean --ccache --state-dir="$TOP_DIR/.flatpak-builder" --install-deps-from=flathub builddir org.flatpak.Builder.json
rm -rf "builddir/files/lib/debug"

cd "$TOP_DIR"/docker
docker build -t linter:dev -f Dockerfile .
rm -rf org.flatpak.Builder

cd "$TOP_DIR"
docker run --pull never -it --rm --entrypoint= -v "$(pwd)":/mnt:Z -w /mnt linter:dev bash
