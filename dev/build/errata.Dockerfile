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

FROM base as statics-collector
 # Collect statics
RUN DJANGO_SETTINGS_MODULE=errata_orject.settings.base ./manage.py collectstatic --no-input

FROM ghcr.io/nginx/nginx-unprivileged:1.29 as statics
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

# install the static files
COPY --from=statics-collector /workspace/static /usr/share/nginx/html/static/

# listen on port 8042 instead of 8080
RUN sed --in-place 's/8080/8042/' /etc/nginx/conf.d/default.conf

FROM base as backend
COPY docker/scripts/app-init.sh /docker-init.sh
RUN sed -i 's/\r$//' /docker-init.sh && chmod +rx /docker-init.sh
ENV DJANGO_SETTINGS_MODULE=errata_project.settings.prod

COPY . .
COPY ./dev/build/start.sh ./start.sh
COPY ./dev/build/backend-start.sh ./backend-start.sh
COPY ./dev/build/migration-start.sh ./migration-start.sh
COPY ./dev/build/gunicorn.conf.py ./gunicorn.conf.py

RUN pip3 --disable-pip-version-check --no-cache-dir install -r requirements.txt

RUN chmod +x start.sh && \
    chmod +x backend-start.sh && \
    chmod +x migration-start.sh

CMD ["./start.sh"]

EXPOSE 8000
