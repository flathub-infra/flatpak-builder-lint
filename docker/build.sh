#!/bin/bash
set -e

sudo apt-get update
sudo apt-get install -y flatpak-builder git bzip2 git \
    python3 python3-requirement-parser python3-toml

git config --global protocol.file.allow always

flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
[[ ! -d org.flatpak.Builder ]] && git clone https://github.com/flathub/org.flatpak.Builder

mv flatpak-builder-lint-deps.json org.flatpak.Builder/flatpak-builder-lint-deps.json
python3 rewrite-manifest.py

case $1 in
    linux/amd64)
        arch=x86_64
        ;;
    linux/arm64)
        arch=aarch64
        ;;
esac

cd org.flatpak.Builder 
flatpak-builder --arch=$arch --user --verbose --force-clean --repo=repo \
    --ccache --install-deps-from=flathub builddir org.flatpak.Builder.json
rm -rf "builddir/files/lib/debug"
