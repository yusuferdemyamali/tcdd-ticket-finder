## Context

See `proposal.md` for motivation. The current runtime has a single `app` service in `docker-compose.yml`, runtime-only app secrets, a named SQLite data volume, and no exposed app ports. The existing TCDD provider uses `httpx` inside `app/tcdd/` for station CDN and train availability requests, while Telegram, monitoring, and persistence are separate application concerns.

The requested deployment path needs an outbound proxy only for TCDD endpoints. It must not set `HTTP_PROXY`, `HTTPS_PROXY`, or similar process-wide proxy variables for the app container because that would also affect Telegram or unrelated HTTP clients.

## Goals / Non-Goals

**Goals:**

- Add a `tailscale` Compose sidecar that exposes `http://tailscale:1055` inside the Compose network.
- Keep Tailscale auth key, exit node, and state as runtime concerns, with persistent sidecar state on a named volume.
- Ensure the app service passes `TCDD_PROXY_URL=http://tailscale:1055` as TCDD-provider configuration only.
- Preserve existing Telegram API, SQLite, monitoring, TCDD parsing, and TCDD token semantics.
- Provide deploy-time verification steps for generic HTTPS, TCDD station CDN, station lookup, and train search.

**Non-Goals:**

- No host networking, privileged mode, `/dev/net/tun`, or whole-container proxying.
- No TCDD token refresh, public proxy fallback, rotating proxy, Telegram webhook changes, monitoring interval changes, Kubernetes, or CI/CD.
- No new generic proxy abstraction outside the TCDD provider path.

## Decisions

1. Use a Compose sidecar named `tailscale` with the official image.

   Rationale: This keeps Tailscale operational concerns outside the Python application image and matches Coolify's sidecar deployment model. The app reaches the proxy by Compose service DNS at `tailscale`.

   Alternative considered: Install Tailscale in the app image. Rejected because it mixes network-agent lifecycle, auth state, and app runtime into one image and increases the chance of baking secrets or state into the wrong layer.

2. Use Tailscale userspace networking and outbound HTTP proxy mode.

   Rationale: `TS_USERSPACE=true` with `TS_OUTBOUND_HTTP_PROXY_LISTEN=:1055` avoids host networking, privileged mode, and `/dev/net/tun` while providing the HTTP proxy contract the TCDD provider needs.

   Alternative considered: Kernel networking with `/dev/net/tun`. Rejected because the requested scope says userspace mode is enough if possible and avoids broader container privileges.

3. Configure the phone exit node through runtime environment variables.

   Rationale: `TAILSCALE_AUTHKEY` and `TAILSCALE_EXIT_NODE` differ per deployment and are sensitive or environment-specific. Compose should pass them to the sidecar as `TS_AUTHKEY` and `TS_EXTRA_ARGS=--exit-node=${TAILSCALE_EXIT_NODE}` without hardcoding values.

   Alternative considered: Commit a fixed exit node name or IP. Rejected because it exposes environment-specific details and makes redeploys less portable.

4. Scope proxy usage inside the TCDD provider instead of the container environment.

   Rationale: The requirement is to route only TCDD traffic. The implementation should read `TCDD_PROXY_URL` when constructing the HTTP client used by `app/tcdd/` requests, not set global proxy variables that `python-telegram-bot` or other libraries might automatically honor.

   Alternative considered: Set `HTTPS_PROXY` on the app service. Rejected because it would likely proxy Telegram API calls and any other outbound HTTP traffic.

5. Keep Tailscale state on a dedicated named volume.

   Rationale: `TS_STATE_DIR=/var/lib/tailscale` backed by a named volume lets the sidecar survive restart/redeploy without re-baking credentials into the image and reduces repeated auth work.

   Alternative considered: Stateless sidecar auth every start. Rejected because it creates avoidable tailnet churn and depends more heavily on auth-key availability.

## Risks / Trade-offs

- Current Python code may not yet read `TCDD_PROXY_URL` -> Mitigation: during implementation, first inspect `app/tcdd/` client construction and add the smallest scoped `httpx` proxy wiring only if missing.
- Tailscale image environment names may differ by image version -> Mitigation: use the documented `tailscale/tailscale` container variables from the requested architecture and verify with `docker compose config` plus a Coolify terminal smoke test.
- Phone exit node can be offline or not advertising exit-node capability -> Mitigation: treat proxy connection failures as existing typed TCDD failures and verify the exit node from the tailnet before production rollout.
- HTTP proxy readiness may lag app startup -> Mitigation: do not change monitoring intervals or app lifecycle; rely on existing TCDD outage semantics and add manual deploy verification for proxy reachability.
- `openspec/config.yaml` currently emits a parse warning -> Mitigation: keep this change scoped to planning/runtime artifacts and report the warning separately if validation output is affected.

## Migration Plan

1. Add runtime values in Coolify for `TAILSCALE_AUTHKEY`, `TAILSCALE_EXIT_NODE`, and `TCDD_PROXY_URL=http://tailscale:1055`.
2. Deploy the Compose stack so `app` and `tailscale` run on the same Compose network and Tailscale state is mounted from its named volume.
3. From the app container, verify `http://tailscale:1055` can fetch `https://example.com` and the TCDD station CDN URL.
4. Run provider smoke checks for `TcddClient().get_station("Eskisehir")` and a representative `TcddClient().search_trains(...)` call.
5. Roll back by removing `TCDD_PROXY_URL` from the app runtime environment and stopping/removing the sidecar service while leaving the existing app and SQLite volume behavior unchanged.
