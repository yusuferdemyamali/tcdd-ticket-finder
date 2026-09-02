## 1. TCDD Proxy Scoping

- [x] 1.1 Inspect `app/tcdd/` HTTP client construction for existing `TCDD_PROXY_URL` support and verify whether station CDN and train-availability requests can be proxied without touching Telegram, persistence, or monitoring code.
- [x] 1.2 If `TCDD_PROXY_URL` support is missing or incomplete, add the smallest TCDD-provider-only proxy wiring and verify unit tests cover configured-proxy and unset-proxy behavior.
- [x] 1.3 Verify proxy connection failures still map to existing typed TCDD errors and do not return empty station or train results.

## 2. Compose Sidecar Runtime

- [x] 2.1 Extend `docker-compose.yml` with a `tailscale` service using the official `tailscale/tailscale` image and verify `docker compose config` renders the service.
- [x] 2.2 Configure the sidecar runtime environment with `TS_AUTHKEY=${TAILSCALE_AUTHKEY}`, `TS_STATE_DIR=/var/lib/tailscale`, `TS_USERSPACE=true`, `TS_OUTBOUND_HTTP_PROXY_LISTEN=:1055`, and `TS_EXTRA_ARGS=--exit-node=${TAILSCALE_EXIT_NODE}` and verify no auth key or exit node value is hardcoded.
- [x] 2.3 Add a persistent Tailscale state volume mounted at `/var/lib/tailscale` and verify the rendered Compose config includes the mount and named volume.
- [x] 2.4 Configure the app service with `TCDD_PROXY_URL=${TCDD_PROXY_URL:-http://tailscale:1055}` or the project’s established equivalent and verify no global `HTTP_PROXY` or `HTTPS_PROXY` is set for the app service.

## 3. Environment Documentation And Secret Safety

- [x] 3.1 Add `.env.example` placeholders for `TAILSCALE_AUTHKEY=`, `TAILSCALE_EXIT_NODE=`, and `TCDD_PROXY_URL=http://tailscale:1055` and verify the file contains no real secrets.
- [x] 3.2 Inspect `Dockerfile`, `docker-compose.yml`, `.env.example`, and touched code for hardcoded `TAILSCALE_AUTHKEY`, `TAILSCALE_EXIT_NODE`, `TCDD_TOKEN`, `TELEGRAM_BOT_TOKEN`, or `TELEGRAM_ALLOWED_USER_ID` values.
- [x] 3.3 Verify no build arguments or image-layer configuration are introduced for Tailscale auth key, exit node, Telegram token, or TCDD token.

## 4. Verification

- [x] 4.1 Run the existing test suite and verify it passes without changing Telegram search flow, SQLite persistence, monitoring intervals, TCDD parser behavior, or TCDD token semantics.
- [x] 4.2 In a running Compose/Coolify environment, verify `http://tailscale:1055` can fetch `https://example.com` with HTTP 200 from the app container network.
- [x] 4.3 In a running Compose/Coolify environment, verify `http://tailscale:1055` can fetch `https://cdn-api-prod-ytp.tcddtasimacilik.gov.tr/datas/station-pairs-INTERNET.json` with HTTP 200.
- [x] 4.4 In production-like runtime configuration, verify `TcddClient().get_station("Eskisehir")` returns a canonical station through the proxy.
- [x] 4.5 In production-like runtime configuration, verify `TcddClient().search_trains(...)` returns normalized train availability results through the proxy.
