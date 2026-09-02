## Why

Coolify production cannot reliably connect directly to TCDD endpoints because TLS handshakes time out, while the same endpoints work from a local Turkey-based connection. Routing only TCDD HTTP traffic through a Tailscale sidecar and phone exit node should restore TCDD access without changing Telegram, SQLite, or monitoring behavior.

## What Changes

- Extend the existing Compose runtime with a `tailscale` sidecar service using the official `tailscale/tailscale` image.
- Configure the sidecar for userspace networking, a container-network HTTP outbound proxy on port `1055`, a persistent Tailscale state volume, and a runtime-selected exit node.
- Add runtime environment placeholders for `TAILSCALE_AUTHKEY`, `TAILSCALE_EXIT_NODE`, and `TCDD_PROXY_URL=http://tailscale:1055`.
- Configure the app service so TCDD provider traffic can use `TCDD_PROXY_URL` while Telegram API and other non-TCDD traffic remain direct.
- Keep auth key, exit node, TCDD token, and Telegram secrets out of committed files, image layers, and logs.
- Do not add token refresh, public proxy fallback, rotating proxies, host networking, privileged mode, `/dev/net/tun`, Kubernetes, CI/CD, or whole-container proxying.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `container-runtime`: Adds the Tailscale sidecar, persistent sidecar state, runtime-only sidecar configuration, and the app-to-sidecar network contract needed for Coolify deployment.
- `tcdd-provider`: Requires the production TCDD provider to use `TCDD_PROXY_URL` only for TCDD endpoint requests when configured, without proxying Telegram or unrelated application traffic.

## Impact

- Affects `docker-compose.yml` and `.env.example` runtime configuration.
- Affects `app/tcdd/` HTTP client construction only if existing `TCDD_PROXY_URL` support is incomplete.
- Adds a persistent Compose volume for Tailscale state.
- Does not change Telegram handlers, SQLite schema or persistence behavior, monitoring intervals, TCDD parsing, TCDD token handling, or train availability normalization.
