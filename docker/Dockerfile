FROM docker.io/freedesktopsdk/sdk:24.08

RUN echo "root:x:0:0:root:/root:/bin/bash" > /etc/passwd && \
    echo "root:x:0:" > /etc/group

RUN mkdir -p -m 1777 /var/tmp && mkdir -p -m 700 /root

ENV PATH="/app/bin:$PATH"
ENV LD_LIBRARY_PATH=/app/lib
ENV PYTHONPATH=/app/lib/python3.12/site-packages
ENV GI_TYPELIB_PATH=/app/lib/girepository-1.0

ADD org.flatpak.Builder/builddir/files /app

ENTRYPOINT ["/app/bin/flatpak-builder-lint"]
