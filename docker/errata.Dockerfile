FROM python:3.12-trixie as base
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update --fix-missing && \
    apt-get install -qy --no-install-recommends \
        postgresql-client-17 
COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install --no-warn-script-location -r /tmp/pip-tmp/requirements.txt && rm -rf /tmp/pip-tmp
RUN groupadd --force --gid 1000 notroot && \
    useradd -s /bin/bash --uid 1000 --gid 1000 -m notroot

FROM base as app
ENV DJANGO_SETTINGS_MODULE=errata_project.settings.prod

FROM app as app-dev
ENV DJANGO_SETTINGS_MODULE=errata_project.settings.dev

FROM base as celery
COPY docker/scripts/celery-init.sh /docker-init.sh
RUN sed -i 's/\r$//' /docker-init.sh && chmod +rx /docker-init.sh
RUN pip3 --disable-pip-version-check --no-cache-dir install --no-warn-script-location watchdog[watchmedo]
ENV DJANGO_SETTINGS_MODULE=errata_project.settings.prod
ENV CELERY_UID=1000
ENV CELERY_GID=1000
ENTRYPOINT ["/docker-init.sh"]

FROM celery as celery-dev
ENV DJANGO_SETTINGS_MODULE=errata_project.settings.dev
ENV DEV_MODE=True
