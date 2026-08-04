# Production deployment

The production Compose profile terminates TLS at Traefik and fails closed when required secrets or the public origin are missing.

## Required values

Create an untracked `.env` file or inject equivalent environment variables through the deployment platform:

```dotenv
POSTGRES_PASSWORD=<long-random-database-password>
PUBLIC_ORIGIN=https://erd.example.com
TLS_CERTIFICATE_FILE=/absolute/path/to/fullchain.pem
TLS_PRIVATE_KEY_FILE=/absolute/path/to/private-key.pem
TRAEFIK_HTTPS_BIND_ADDRESS=0.0.0.0
TRAEFIK_HTTPS_PORT=443
```

Create `secrets/app_secret` as a high-entropy application secret and restrict all secret files to the deployment identity. Certificate files must contain PEM-encoded material whose subject alternative names cover the public host in `PUBLIC_ORIGIN`.

## Validate before starting

```bash
docker compose --env-file .env -f compose.prod.yaml config --quiet
docker compose --env-file .env -f compose.prod.yaml up --build -d
```

The public application endpoint is HTTPS only. The cleartext entry point is bound to loopback by default and permanently redirects to the HTTPS entry point. When an upstream load balancer terminates TLS instead, do not expose this profile's cleartext port publicly; preserve an authenticated, encrypted hop or replace the profile with an equivalently tested deployment module.

## Verification

Verify the deployed endpoint with a client that checks certificate validity:

```bash
curl --fail --show-error --silent --location https://erd.example.com/healthz
curl --fail --show-error --silent --head https://erd.example.com/ | grep -i strict-transport-security
```

A deployment is not release-ready when it relies on Traefik's generated self-signed certificate, omits the required public HTTPS origin, or exposes the backend service directly.
