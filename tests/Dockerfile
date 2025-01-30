FROM archlinux:latest@sha256:901cf83a14f09d9ba70b219e22f67abd4d6346cb6d3f0c048cd08f22fb9a7425 AS base

RUN echo "Server=https://archive.archlinux.org/repos/2024/12/21/\$repo/os/\$arch" > /etc/pacman.d/mirrorlist

RUN echo -e "keyserver-options auto-key-retrieve" >> /etc/pacman.d/gnupg/gpg.conf && \
    sed -i '/CheckSpace/s/^/#/g' /etc/pacman.conf && \
    sed -i '/OPTIONS/s/debug/!debug/g' /etc/makepkg.conf && \
    pacman-key --init && \
    pacman --noconfirm -Syyuu

RUN pacman --noconfirm --needed -S \
    base base-devel \
    git appstream flatpak-builder \
    desktop-file-utils ostree glib2 \
    meson ninja jq gperf glib2-devel gobject-introspection itstool \
    xmlto docbook-xsl docbook-xml python-pip python-pipx

FROM base AS image

RUN git clone --depth 1 --branch master https://github.com/flathub/org.flatpak.Builder.git

WORKDIR /org.flatpak.Builder
RUN version="$(jq -r '.modules[] | select(type == "object" and .name == "appstream") .sources[].url | select(. != null)' org.flatpak.Builder.json | xargs -n1 basename | sed "s/.tar.*$//")" \
    && echo "$version" > /version.txt

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
        -Dgir=true \
        -Dstemming=false \
        -Dsystemd=false \
        -Dvapi=false \
        -Dqt=false \
        -Dcompose=false \
        -Dapt-support=false \
        -Dsvg-support=false \
        -Dzstd-support=false \
        -Ddocs=false \
        -Dapidocs=false \
        -Dinstall-docs=false \
        -Dtests=false \
        -Dinstalled_tests=false \
        && meson compile -C builddir

RUN pacman --noconfirm -Rdd appstream && meson install -C builddir

WORKDIR /

RUN pipx install poetry && pipx inject poetry poetry-plugin-export

COPY . /flatpak-builder-lint

WORKDIR /flatpak-builder-lint
RUN rm -f requirements.txt && \
    /root/.local/bin/poetry export --with dev --output requirements.txt
    
RUN pip install --ignore-installed --break-system-packages -r requirements.txt
RUN pip install --break-system-packages .
RUN rm -rf /org.flatpak.Builder /appstream /version.txt /flatpak-builder-lint/requirements.txt

WORKDIR /flatpak-builder-lint
