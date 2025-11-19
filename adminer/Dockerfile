ARG IC_BASIC_URL=https://download.oracle.com/otn_software/linux/instantclient/2390000/instantclient-basiclite-linux.x64-23.9.0.25.07.zip
ARG IC_SDK_URL=https://download.oracle.com/otn_software/linux/instantclient/2390000/instantclient-sdk-linux.x64-23.9.0.25.07.zip

########################
# Stage 1: builder
########################
FROM adminer:latest AS builder

USER root
# Paquets système et deps de build (autoconf, make, gcc, phpize, etc.)
RUN set -eux; \
    if command -v apk >/dev/null 2>&1; then \
        apk add --no-cache curl unzip ca-certificates libaio libnsl libc6-compat $PHPIZE_DEPS; \
    elif command -v apt-get >/dev/null 2>&1; then \
        apt-get update; \
        apt-get install -y --no-install-recommends curl unzip ca-certificates libaio1 libnsl-dev libc6 $PHPIZE_DEPS; \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo "Unsupported base image: no apk or apt-get found"; exit 1; \
    fi

# Téléchargements Oracle (SDK requis uniquement pour la compilation)
ARG IC_BASIC_URL
ARG IC_SDK_URL
RUN --mount=type=cache,target=/root/.cache \
    curl -fSL "$IC_BASIC_URL" -o /tmp/ic-basic.zip && \
    curl -fSL "$IC_SDK_URL" -o /tmp/ic-sdk.zip

# Installer Instant Client (Basic + SDK) pour compiler oci8
RUN mkdir -p /opt/oracle && cd /opt/oracle && \
    unzip -o /tmp/ic-basic.zip && \
    unzip -o /tmp/ic-sdk.zip && \
    rm -f /tmp/ic-*.zip && \
    mkdir -p /opt/oracle/instantclient_23_9/network/admin

ENV LD_LIBRARY_PATH=/opt/oracle/instantclient_23_9:/lib
ENV TNS_ADMIN=/opt/oracle/instantclient_23_9/network/admin

# Compiler et activer oci8 dans le builder
RUN set -eux; \
    echo "instantclient,/opt/oracle/instantclient_23_9" | pecl install oci8 && \
    docker-php-ext-enable oci8

# Localiser l’extension compilée dynamiquement (le sous-dossier dépend de l’API PHP)
RUN php -i | grep ^extension_dir

########################
# Stage 2: final minimal
########################
FROM adminer:latest AS final

USER root
# Dépendances runtime seulement (pas de $PHPIZE_DEPS)
RUN set -eux; \
    if command -v apk >/dev/null 2>&1; then \
        apk add --no-cache curl unzip ca-certificates libaio libnsl libc6-compat; \
    elif command -v apt-get >/dev/null 2>&1; then \
        apt-get update; \
        apt-get install -y --no-install-recommends curl unzip ca-certificates libaio1 libnsl-dev libc6; \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo "Unsupported base image: no apk or apt-get found"; exit 1; \
    fi

ARG IC_BASIC_URL
# Seul le Basic Lite en final (pas de SDK)
RUN --mount=type=cache,target=/root/.cache \
    curl -fSL "$IC_BASIC_URL" -o /tmp/ic-basic.zip

RUN mkdir -p /opt/oracle && cd /opt/oracle && \
    unzip -o /tmp/ic-basic.zip && \
    rm -f /tmp/ic-basic.zip && \
    mkdir -p /opt/oracle/instantclient_23_9/network/admin

ENV LD_LIBRARY_PATH=/opt/oracle/instantclient_23_9:/lib
ENV TNS_ADMIN=/opt/oracle/instantclient_23_9/network/admin

# Copier l’extension compilée depuis le builder (chemin agnostique via wildcard)
# oci8.so
COPY --from=builder /usr/local/lib/php/extensions/*/oci8.so /usr/local/lib/php/extensions/oci8/oci8.so
# Activer l’extension via un ini dédié
RUN echo "; Enable OCI8 extension" > /usr/local/etc/php/conf.d/docker-oci8.ini && \
    echo "extension=/usr/local/lib/php/extensions/oci8/oci8.so" >> /usr/local/etc/php/conf.d/docker-oci8.ini

USER adminer
