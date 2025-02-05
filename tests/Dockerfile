FROM alpine:latest AS base

RUN apk update && apk add build-base appstream cairo-dev curl-dev \
	fontconfig-dev gdk-pixbuf-dev glib-dev gobject-introspection-dev \
	libxml2-dev libxmlb-dev pango-dev yaml-dev desktop-file-utils \
	flatpak flatpak-builder git glib gobject-introspection gperf \
	itstool jq meson ninja ostree py3-pip pipx py3-cairo-dev libffi-dev \
	py3-setuptools python3-dev libxml2-dev libxslt-dev py3-setuptools \
	cython libxml2 libxslt ostree-gir

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

RUN meson install -C builddir

RUN pipx install poetry && pipx inject poetry poetry-plugin-export

WORKDIR /
COPY . /flatpak-builder-lint

WORKDIR /flatpak-builder-lint
RUN /root/.local/bin/poetry export --with dev --output requirements.txt && \
    pip install --ignore-installed --break-system-packages -r requirements.txt && \
    pip install --break-system-packages .

WORKDIR /flatpak-builder-lint
