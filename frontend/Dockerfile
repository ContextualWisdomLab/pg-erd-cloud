FROM node:25.8.2-alpine@sha256:cf38e1f3c28ac9d81cdc0c51d8220320b3b618780e44ef96a39f76f7dbfef023

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
