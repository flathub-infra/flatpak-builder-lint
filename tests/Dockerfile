FROM archlinux:latest@sha256:901cf83a14f09d9ba70b219e22f67abd4d6346cb6d3f0c048cd08f22fb9a7425 AS base

RUN echo "Server=https://archive.archlinux.org/repos/2024/12/21/\$repo/os/\$arch" > /etc/pacman.d/mirrorlist

RUN pacman --noconfirm -Syyuu && pacman --noconfirm --needed -S \
    appstream base-devel desktop-file-utils flatpak-builder \
    git glib2 glib2-devel gobject-introspection gperf itstool \
    jq meson ninja ostree \
    python-pip python-pipx

FROM base AS image

RUN git clone --depth 1 https://github.com/flathub/org.flatpak.Builder.git

WORKDIR /org.flatpak.Builder
RUN jq -r '.modules[] | select(type == "object" and .name == "appstream") .sources[].url | select(. != null)' \
    org.flatpak.Builder.json | xargs -n1 basename | sed "s/.tar.*$//" > /version.txt

WORKDIR /
RUN git clone --branch "$(cat /version.txt)" --depth 1 https://github.com/ximion/appstream.git

WORKDIR /appstream
RUN cp -vf ../org.flatpak.Builder/patches/appstream-*.patch . && \
    for patch in appstream-*.patch; do \
        patch -Np1 -i "$patch"; \
    done && \
    meson setup builddir \
        --prefix=/usr \
        --libexecdir=lib \
        -Dapidocs=false \
        -Dapt-support=false \
        -Dcompose=false \
        -Ddocs=false \
        -Dgir=true \
        -Dinstall-docs=false \
        -Dinstalled_tests=false \
        -Dqt=false \
        -Dstemming=false \
        -Dsvg-support=false \
        -Dsystemd=false \
        -Dtests=false \
        -Dvapi=false \
        -Dzstd-support=false \
        && meson compile -C builddir

RUN pacman --noconfirm -Rdd appstream && meson install -C builddir

RUN pipx install poetry && pipx inject poetry poetry-plugin-export

WORKDIR /
COPY . /flatpak-builder-lint

WORKDIR /flatpak-builder-lint
RUN /root/.local/bin/poetry export --with dev --output requirements.txt && \
    pip install --ignore-installed --break-system-packages -r requirements.txt && \
    pip install --break-system-packages .

WORKDIR /flatpak-builder-lint
