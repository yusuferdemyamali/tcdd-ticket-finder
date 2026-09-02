# container-runtime Specification

## Purpose
Provide a reproducible Docker runtime for the TCDD Ticket Finder MVP that starts the Telegram bot and monitoring lifecycle while keeping secrets out of the image and preserving SQLite data on a mounted volume.

## Requirements

### Requirement: Container image provides production runtime
The system SHALL provide a Docker image based on Python 3.12 or newer that installs the production dependencies needed to run the TCDD Ticket Finder bot.

The image SHALL avoid unnecessary development tooling and SHALL NOT bake Telegram or TCDD secret values into the image or image layers.

#### Scenario: Docker image builds successfully
- **WHEN** the Docker image is built from the repository Dockerfile
- **THEN** the build succeeds with a Python 3.12 or newer runtime
- **AND** production dependencies needed by Telegram handling, monitoring, SQLite persistence, and TCDD access are installed

#### Scenario: Secrets are not baked into the image
- **WHEN** the Docker image is built
- **THEN** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_ID`, and `TCDD_TOKEN` are not hardcoded in the Dockerfile or image build instructions

### Requirement: Compose runtime starts bot and monitoring lifecycle
The system SHALL provide Docker Compose configuration that can start the application with the normal Telegram bot lifecycle and the existing monitoring lifecycle.

The runtime SHALL accept required configuration through environment variables provided at container startup.

#### Scenario: Compose starts the application
- **WHEN** `docker compose up` is run with required environment variables supplied
- **THEN** the application container starts successfully
- **AND** Telegram bot handling starts
- **AND** automatic ticket monitoring starts using the existing lifecycle behavior

#### Scenario: Runtime configuration comes from environment
- **WHEN** the Compose service is configured for startup
- **THEN** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_ID`, `TCDD_TOKEN`, and `DATABASE_PATH` can be provided through environment variables
- **AND** real secret values are not hardcoded in `docker-compose.yml`

### Requirement: Compose persists SQLite data on a volume
The Compose runtime SHALL store the SQLite database file under a mounted persistent volume path and SHALL configure `DATABASE_PATH` to point to that location.

#### Scenario: Database is created on persistent volume
- **WHEN** the application starts with an empty persistent volume
- **THEN** SQLite initialization creates the ticket-search database file under the configured volume path

#### Scenario: Recreated container preserves database file
- **WHEN** the application container is recreated while the persistent volume remains
- **THEN** the same SQLite database file remains available to the application after startup

### Requirement: Example environment documents required configuration
The repository SHALL include an example environment file that documents the runtime environment variables required to run the Compose service and the TCDD-only Tailscale proxy path, using placeholders only.

#### Scenario: Example environment contains placeholders only
- **WHEN** `.env.example` is inspected
- **THEN** it lists the required runtime variables for Telegram, TCDD, SQLite database path, monitoring configuration, Tailscale authentication, Tailscale exit-node selection, and TCDD proxy URL configuration
- **AND** it includes placeholders for `TAILSCALE_AUTHKEY`, `TAILSCALE_EXIT_NODE`, and `TCDD_PROXY_URL=http://tailscale:1055`
- **AND** it does not contain real Telegram bot tokens, Telegram user ids, TCDD tokens, Tailscale auth keys, exit node identifiers, or other secret values

### Requirement: Container scope remains limited to MVP runtime
The containerization change SHALL NOT introduce deployment platforms, ingress components, dashboards, backup automation, or new ticket-search application behavior.

The only proxy component allowed by this runtime is the Tailscale sidecar outbound HTTP proxy used for TCDD endpoint access. The runtime SHALL NOT proxy all container traffic or add public proxy, rotating proxy, reverse-proxy ingress, Kubernetes, CI/CD, monitoring dashboard, backup, or web-panel behavior.

#### Scenario: Out-of-scope deployment features are absent
- **WHEN** the containerization artifacts are reviewed
- **THEN** they do not add CI/CD pipeline configuration, Kubernetes manifests, reverse-proxy ingress configuration, public proxy fallback, rotating proxy configuration, cloud deployment configuration, monitoring dashboards, automated backup systems, or web panel behavior
- **AND** any proxy configuration is limited to the TCDD-only Tailscale sidecar path

### Requirement: Compose routes TCDD traffic through a Tailscale sidecar
The Compose runtime SHALL include a `tailscale` sidecar service that provides an outbound HTTP proxy for TCDD traffic from the application container.

The sidecar SHALL use the official `tailscale/tailscale` image, userspace networking, a container-network HTTP proxy listener, runtime-provided Tailscale authentication, a runtime-provided exit node, and persistent state storage. The runtime SHALL NOT require host networking, privileged mode, or `/dev/net/tun` for this sidecar.

#### Scenario: Sidecar starts with runtime-only Tailscale configuration
- **WHEN** the Compose stack is started with `TAILSCALE_AUTHKEY` and `TAILSCALE_EXIT_NODE` supplied at runtime
- **THEN** the `tailscale` service joins the tailnet using those runtime values
- **AND** the auth key and exit node are not hardcoded in `docker-compose.yml`, committed environment examples, or image build instructions

#### Scenario: Sidecar exposes an internal HTTP proxy
- **WHEN** the Compose stack is running
- **THEN** the application container can reach an HTTP outbound proxy at `http://tailscale:1055` on the Compose network
- **AND** the proxy can fetch general HTTPS URLs through the selected Tailscale exit node

#### Scenario: App config points TCDD traffic at the sidecar
- **WHEN** the app service is created by Compose
- **THEN** `TCDD_PROXY_URL` can be set to `http://tailscale:1055` through runtime environment configuration
- **AND** the app container remains on the same Compose network as the `tailscale` sidecar

#### Scenario: Telegram traffic is not routed through the sidecar
- **WHEN** the Compose stack runs with `TCDD_PROXY_URL=http://tailscale:1055`
- **THEN** the runtime does not configure a global container proxy for all application traffic
- **AND** Telegram API traffic continues to use direct outbound internet access

#### Scenario: Tailscale state survives sidecar recreation
- **WHEN** the `tailscale` service is restarted or recreated while its persistent volume remains
- **THEN** Tailscale state remains available under the configured state directory
- **AND** the sidecar can re-authenticate or resume tailnet membership without baking credentials into the image
