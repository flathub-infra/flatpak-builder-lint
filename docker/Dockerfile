# syntax=docker/dockerfile:1-labs
FROM ubuntu as builder

RUN apt-get update && apt-get install -y bzip2 flatpak-builder git python3 python3-requirement-parser python3-toml

RUN mkdir -p /build
COPY build.sh rewrite-manifest.py flatpak-builder-lint-deps.json /build/
WORKDIR /build
RUN --security=insecure bash -x ./build.sh


FROM docker.io/freedesktopsdk/sdk:23.08
COPY --from=builder /build/org.flatpak.Builder/builddir/files /app

ENV PATH="/app/bin:$PATH"
ENV LD_LIBRARY_PATH=/app/lib
ENV PYTHONPATH=/app/lib/python3.11/site-packages
ENV GI_TYPELIB_PATH=/app/lib/girepository-1.0

ENTRYPOINT ["/app/bin/flatpak-builder-lint"]
