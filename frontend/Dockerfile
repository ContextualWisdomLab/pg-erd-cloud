FROM node:26.5.0-alpine@sha256:e88a35be04478413b7c71c455cd9865de9b9360e1f43456be5951032d7ac1a66

WORKDIR /app

# Ensure the non-root `node` user can write to /app (e.g. for node_modules).
RUN chown -R node:node /app

COPY --chown=node:node package.json package-lock.json /app/

USER node

RUN npm ci

COPY --chown=node:node . /app

EXPOSE 5173

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:5173/ || exit 1

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
