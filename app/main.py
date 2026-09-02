from __future__ import annotations

import logging
import os
import pathlib
import sqlite3

from app.database import get_connection
from app.monitoring.config import load_monitoring_config
from app.tcdd.client import TcddClient
from app.telegram.bot import build_application_with_monitoring
from app.telegram.config import load_telegram_config
from app.ticket_searches.repository import TicketSearchRepository
from app.ticket_searches.service import TicketSearchService

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = "data/tcdd-ticket.sqlite3"


def get_database_path(env: dict | None = None) -> str:
    """Resolve DATABASE_PATH from environment with safe fallback.

    Returns a non-empty file path. If DATABASE_PATH is missing or blank,
    falls back to DEFAULT_DATABASE_PATH. This keeps startup resilient when
    operator provides an empty value and still yields a readable SQLite file.
    """
    source = env if env is not None else os.environ
    try:
        raw = source.get("DATABASE_PATH")  # type: ignore[attr-defined]
    except Exception:
        raw = None
    if raw is None:
        return DEFAULT_DATABASE_PATH
    s = str(raw).strip()
    if not s:
        return DEFAULT_DATABASE_PATH
    return s


def ensure_database_directory(db_path: str) -> str:
    """Create parent directory for db_path if needed; return validated path.

    No-op for ":memory:". Handles absolute and relative paths, including
    container volume path /data/tcdd-ticket.sqlite3. Idempotent.
    """
    if db_path == ":memory:":
        return db_path
    # Empty already handled by get_database_path, but guard anyway
    if not db_path or not str(db_path).strip():
        db_path = DEFAULT_DATABASE_PATH
    p = pathlib.Path(db_path)
    parent = p.parent
    # parent may be '.' for file in current dir; only mkdir if meaningful
    if str(parent) not in ("", "."):
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Failed to create database directory %s: %s", parent, e)
            raise
    # Also handle case where default path uses 'data/' and '.' didn't create data
    # Already handled via parent != '.' check above creates 'data'
    return db_path


def get_connection_for_path(db_path: str | None = None) -> sqlite3.Connection:
    """Create or validate SQLite connection for given path.

    Ensures parent directory exists, then delegates to app.database.get_connection
    which also runs init_db (creates ticket_searches table + index).
    """
    if db_path is None:
        db_path = get_database_path()
    db_path = ensure_database_directory(db_path)
    conn = get_connection(db_path)
    return conn


def create_ticket_service(
    db_path: str | None = None,
    conn: sqlite3.Connection | None = None,
    now_fn=None,
) -> tuple[TicketSearchService, sqlite3.Connection]:
    """Build TicketSearchService from DB path or existing connection."""
    if conn is None:
        conn = get_connection_for_path(db_path)
    repo = TicketSearchRepository(conn)
    service = TicketSearchService(repo, now=now_fn)
    return service, conn


def create_tcdd_client() -> TcddClient:
    """Build production TcddClient (httpx-based, optional curl_cffi fallback)."""
    return TcddClient()


def build_application(
    db_path: str | None = None,
    conn: sqlite3.Connection | None = None,
    tcdd_client: TcddClient | None = None,
    now_fn=None,
):
    """Build Telegram Application with monitoring without starting polling.

    Reads DATABASE_PATH, initializes SQLite, builds ticket service,
    TCDD provider, Telegram config, and monitoring. Does not start network
    calls; safe to import and test.
    """
    if db_path is None:
        db_path = get_database_path()
    ticket_service, conn = create_ticket_service(db_path=db_path, conn=conn, now_fn=now_fn)
    if tcdd_client is None:
        tcdd_client = create_tcdd_client()

    telegram_config = load_telegram_config()
    monitoring_config = load_monitoring_config()

    # TcddClient doubles as station_provider via its search_stations method
    station_provider = tcdd_client

    app, monitoring = build_application_with_monitoring(
        token=telegram_config.token,
        allowed_user_id=telegram_config.allowed_user_id,
        ticket_service=ticket_service,
        station_provider=station_provider,
        tcdd_client=tcdd_client,
        monitoring_config=monitoring_config,
        now_fn=now_fn,
    )
    return app, monitoring, ticket_service, conn, tcdd_client


def main() -> None:
    """Production entrypoint: init DB, build services, start Telegram polling + monitoring."""
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("Starting TCDD Ticket Finder Bot")
    db_path = get_database_path()
    logger.info("Using DATABASE_PATH=%s", db_path)
    try:
        db_path = ensure_database_directory(db_path)
        logger.info("Ensured database directory for %s", db_path)
    except Exception as e:
        logger.error("Failed to ensure database directory: %s", e)
        raise

    # Validate DB file can be created/opened before building telegram
    conn = get_connection_for_path(db_path)
    logger.info("SQLite database initialized at %s", db_path)

    # Build app without side-effects beyond DB init and config load
    app, monitoring, ticket_service, conn, tcdd_client = build_application(
        db_path=db_path, conn=conn
    )

    # Log persistence state for recovery visibility without exposing secrets
    try:
        active = ticket_service.get_active_search()
        recovery = ticket_service.list_recovery_searches()
        logger.info("Recovery check: active=%s total_recovery=%s", bool(active), len(recovery))
    except Exception as e:
        logger.warning("Recovery check failed: %s", e)

    logger.info("Starting Telegram polling and monitoring")
    # This blocks until shutdown; post_init will trigger monitoring startup_recovery
    app.run_polling(
        allowed_updates=None,
        close_loop=False,
    )


if __name__ == "__main__":
    main()
