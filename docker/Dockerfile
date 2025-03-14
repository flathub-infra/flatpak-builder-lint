FROM docker.io/freedesktopsdk/sdk:24.08

RUN install -d -m1777 /var/tmp
RUN mkdir -p /root

RUN echo "root:x:0:0:root:/root:/bin/bash" > /etc/passwd && \
    echo "root:x:0:" > /etc/group

ENV PATH="/app/bin:$PATH"
ENV LD_LIBRARY_PATH=/app/lib
ENV PYTHONPATH=/app/lib/python3.12/site-packages
ENV GI_TYPELIB_PATH=/app/lib/girepository-1.0

ADD org.flatpak.Builder/builddir/files /app

ENTRYPOINT ["/app/bin/flatpak-builder-lint"]
