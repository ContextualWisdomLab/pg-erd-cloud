FROM node:26.1.0-alpine@sha256:e71ac5e964b9201072425d59d2e876359efa25dc96bb1768cb73295728d6e4ea

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
