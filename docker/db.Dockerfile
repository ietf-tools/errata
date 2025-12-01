FROM postgres:17
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV POSTGRES_PASSWORD=dev-not-a-secret
ENV POSTGRES_USER=django
ENV POSTGRES_DB=errata
ENV POSTGRES_HOST_AUTH_METHOD=trust