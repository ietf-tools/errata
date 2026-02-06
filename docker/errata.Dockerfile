FROM python:3.12-trixie AS base
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update --fix-missing && \
    apt-get install -qy --no-install-recommends \
        postgresql-client-17 
COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install --no-warn-script-location -r /tmp/pip-tmp/requirements.txt && rm -rf /tmp/pip-tmp
RUN groupadd --force --gid 1000 notroot && \
    useradd -s /bin/bash --uid 1000 --gid 1000 -m notroot

FROM base AS app
COPY docker/scripts/app-init.sh /docker-init.sh
RUN sed -i 's/\r$//' /docker-init.sh && chmod +rx /docker-init.sh
ENV DJANGO_SETTINGS_MODULE=errata_project.settings.prod

FROM app AS app-dev
RUN mv /docker-init.sh /docker-app-init.sh
COPY docker/scripts/app-dev-init.sh /docker-init.sh
RUN sed -i 's/\r$//' /docker-init.sh && chmod +rx /docker-init.sh
ENV DJANGO_SETTINGS_MODULE=errata_project.settings.dev
ENV ERRATA_OIDC_RP_CLIENT_ID=079065
ENV ERRATA_OIDC_RP_CLIENT_SECRET=788eb5a13ee8e233e91a42c88b5ad1736342c5b98e3bcec834d01074

