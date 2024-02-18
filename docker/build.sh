#!/bin/bash
set -e

git config --global protocol.file.allow always

flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
[[ ! -d org.flatpak.Builder ]] && git clone https://github.com/flathub/org.flatpak.Builder

mv flatpak-builder-lint-deps.json org.flatpak.Builder/flatpak-builder-lint-deps.json
python3 rewrite-manifest.py

cd org.flatpak.Builder 
flatpak-builder --user --verbose --force-clean --repo=repo \
    --disable-rofiles-fuse --ccache --install-deps-from=flathub \
    builddir org.flatpak.Builder.json
rm -rf files/lib/debug
