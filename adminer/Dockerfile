FROM adminer:latest

# Dépendances système pour Oracle Instant Client + PECL (Alpine)
# Le conteneur Adminer officiel peut utiliser un utilisateur non-root par défaut.
# On passe en root pour installer les paquets avec apk, puis on peut rester root (minimal change)
USER root
RUN apk add --no-cache libaio libnsl libc6-compat curl unzip ca-certificates $PHPIZE_DEPS \
 && ln -s /lib/libc.so.6 /usr/lib/libresolv.so.2 || true

# Téléchargement automatique des archives Oracle Instant Client
# Vous pouvez surcharger ces URLs via --build-arg IC_BASIC_URL=... et IC_SDK_URL=...
ARG IC_BASIC_URL=https://download.oracle.com/otn_software/linux/instantclient/2390000/instantclient-basiclite-linux.x64-23.9.0.25.07.zip
ARG IC_SDK_URL=https://download.oracle.com/otn_software/linux/instantclient/2390000/instantclient-sdk-linux.x64-23.9.0.25.07.zip
RUN curl -fSL "$IC_BASIC_URL" -o /tmp/instantclient-basiclite-linux.x64-23.9.0.25.07.zip \
 && curl -fSL "$IC_SDK_URL" -o /tmp/instantclient-sdk-linux.x64-23.9.0.25.07.zip

# Installation d’Instant Client dans /opt/oracle
RUN mkdir -p /opt/oracle \
 && cd /opt/oracle \
 && unzip -o /tmp/instantclient-basiclite-linux.x64-23.9.0.25.07.zip \
 && unzip -o /tmp/instantclient-sdk-linux.x64-23.9.0.25.07.zip \
 && rm -f /tmp/instantclient-*.zip \
 && mkdir -p /opt/oracle/instantclient_23_9/network/admin

# Variables d’environnement pour les libs Oracle et TNS
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient_23_9:/lib
ENV TNS_ADMIN=/opt/oracle/instantclient_23_9/network/admin

# Installer l’extension oci8 via PECL
# Le "echo instantclient,..." évite l’invite interactive pendant l’installation
RUN echo "instantclient,/opt/oracle/instantclient_23_9" | pecl install oci8 \
 && docker-php-ext-enable oci8 \
 && apk del --no-network $PHPIZE_DEPS || true

USER adminer