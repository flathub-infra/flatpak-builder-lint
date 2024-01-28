FROM docker.io/freedesktopsdk/sdk:23.08
ADD org.flatpak.Builder/builddir/files /app

ENV PYTHONPATH=/app/lib/python3.11/site-packages
ENV PATH="/app/bin:$PATH"


ENTRYPOINT ["/app/bin/flatpak-builder-lint"]
