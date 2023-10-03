FROM freedesktopsdk/platform:22.08
ADD org.flatpak.Builder/builddir/files /app

ENV PYTHONPATH=/app/lib/python3.10/site-packages
ENV PATH="/app/bin:$PATH"


ENTRYPOINT ["/app/bin/flatpak-builder-lint"]
