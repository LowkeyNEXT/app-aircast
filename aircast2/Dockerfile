ARG BUILD_FROM=ghcr.io/hassio-addons/debian-base:9.2.0
# hadolint ignore=DL3006
FROM ${BUILD_FROM}

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Build arguments
ARG BUILD_ARCH=amd64
ARG NQPTP_VERSION="1.2.4"
ARG SHAIRPORT_SYNC_VERSION="4.3.7"

# hadolint ignore=DL3008,DL3003
RUN \
    apt-get update \
    \
    # Install build dependencies
    && apt-get install -y --no-install-recommends \
        build-essential git autoconf automake libtool pkg-config \
        libmbedtls-dev libpopt-dev libconfig-dev libavahi-client-dev \
        libsodium-dev libgcrypt20-dev libmosquitto-dev libsoxr-dev \
        libplist-dev uuid-dev xxd \
    \
    # Build NQPTP
    && echo "=== Building NQPTP ${NQPTP_VERSION} ===" \
    && git clone --depth 1 --branch "${NQPTP_VERSION}" \
        https://github.com/mikebrady/nqptp.git /tmp/nqptp \
    && cd /tmp/nqptp \
    && autoreconf -fi \
    && ./configure \
    && make -j"$(nproc)" \
    && make install \
    && echo "=== NQPTP installed ===" \
    \
    # Build shairport-sync
    && echo "=== Building shairport-sync ${SHAIRPORT_SYNC_VERSION} ===" \
    && git clone --depth 1 --branch "${SHAIRPORT_SYNC_VERSION}" \
        https://github.com/mikebrady/shairport-sync.git /tmp/shairport-sync \
    && cd /tmp/shairport-sync \
    && autoreconf -fi \
    && ./configure \
        --with-airplay-2 \
        --with-avahi \
        --with-pipe \
        --with-stdout \
        --with-mqtt-client \
        --with-ssl=mbedtls \
        --with-soxr \
        --sysconfdir=/etc \
    && make -j"$(nproc)" \
    && make install \
    && echo "=== shairport-sync installed ===" \
    \
    # Remove build deps, install runtime deps
    && apt-get purge -y --auto-remove \
        build-essential git autoconf automake libtool pkg-config \
        xxd \
    && apt-get install -y --no-install-recommends \
        python3 python3-pip \
        ffmpeg mosquitto \
        avahi-daemon avahi-utils \
        libmbedtls14 libpopt0 libconfig9 libavahi-client3 \
        libsodium23 libgcrypt20 libmosquitto1 libsoxr0 \
        libplist3 \
    && pip3 install --no-cache-dir --break-system-packages \
        pychromecast==14.0.5 \
        paho-mqtt==2.1.0 \
        aiohttp==3.11.11 \
    && echo "=== Python dependencies installed ===" \
    \
    # Verify critical binaries exist
    && shairport-sync --version \
    && nqptp --version || true \
    && echo "=== Build complete ===" \
    \
    # Cleanup
    && rm -fr \
        /tmp/* \
        /var/{cache,log}/* \
        /var/lib/apt/lists/*

# Copy root filesystem
COPY rootfs /

# Build arguments
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

# Labels
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Home Assistant Community Apps" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
