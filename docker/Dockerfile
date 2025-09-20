FROM docker.io/freedesktopsdk/sdk:25.08

RUN echo "root:x:0:0:root:/root:/bin/bash" > /etc/passwd && \
    echo "root:x:0:" > /etc/group

RUN rm -rf /tmp /var/tmp /root /etc/gitconfig && mkdir -p -m 1777 /tmp /var/tmp && \
    mkdir -p -m 700 /root

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PATH="/app/bin:$PATH"
ENV LD_LIBRARY_PATH=/app/lib
ENV PYTHONPATH=/app/lib/python3.13/site-packages
ENV GI_TYPELIB_PATH=/app/lib/girepository-1.0

ADD org.flatpak.Builder/builddir/files /app

ENTRYPOINT ["/app/bin/flatpak-builder-lint"]
