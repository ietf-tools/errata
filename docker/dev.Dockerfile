FROM python:3.12-bookworm
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV DEBIAN_FRONTEND=noninteractive

# Create workspace
RUN mkdir -p /workspace
WORKDIR /workspace

# Copy the startup file
COPY docker/scripts/app-init.sh /docker-init.sh
RUN sed -i 's/\r$//' /docker-init.sh && chmod +rx /docker-init.sh

# Setup non-root user
RUN apt-get update --fix-missing && apt-get install -qy --no-install-recommends sudo
RUN groupadd -g 1000 dev && \
    useradd -c "Dev Datatracker User" -u 1000 -g dev -m -s /bin/false dev && \
    adduser dev sudo && \
    echo "dev ALL=(ALL:ALL) NOPASSWD: ALL" | tee /etc/sudoers.d/dev

# Switch to local dev user
USER dev:dev

# Install current datatracker python dependencies
COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install --user --no-warn-script-location -r /tmp/pip-tmp/requirements.txt
RUN sudo rm -rf /tmp/pip-tmp
ENV PATH=/home/dev/.local/bin:${PATH}
ENV DJANGO_SETTINGS_MODULE=errata_project.settings.dev