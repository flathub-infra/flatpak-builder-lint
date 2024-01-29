FROM docker.io/freedesktopsdk/sdk:23.08
ADD org.flatpak.Builder/builddir/files /app

ENV PATH="/app/bin:$PATH"
ENV LD_LIBRARY_PATH=/app/lib
ENV PYTHONPATH=/app/lib/python3.11/site-packages
ENV GI_TYPELIB_PATH=/app/lib/girepository-1.0

ENTRYPOINT ["/app/bin/flatpak-builder-lint"]
