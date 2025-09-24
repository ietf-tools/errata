FROM node:24
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

RUN mkdir -p /app && \
    chown node:node /app
WORKDIR /app

COPY .output ./
# COPY .data/content/contents.sqlite ./server/

USER node:node
CMD ["node", "server/index.mjs"]