FROM docker.io/freedesktopsdk/sdk:24.08

RUN install -d -m1777 /var/tmp
RUN uuidgen | tr -d '-' > /etc/machine-id
ADD passwd /etc/passwd
RUN install -d -m755 -o 1001 -g 1001 /home/flatbld

ENV PATH="/app/bin:$PATH"
ENV LD_LIBRARY_PATH=/app/lib
ENV PYTHONPATH=/app/lib/python3.12/site-packages
ENV GI_TYPELIB_PATH=/app/lib/girepository-1.0

ADD org.flatpak.Builder/builddir/files /app

RUN ln -s /usr/bin/true /usr/bin/dbus-daemon

USER flatbld
WORKDIR /home/flatbld
ENTRYPOINT ["/app/bin/flatpak-builder-lint"]
