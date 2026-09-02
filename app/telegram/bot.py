from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from .callbacks import RestartCallbackHandler
from .handlers import TelegramHandlers


def build_application(
    token: str,
    allowed_user_id: int,
    ticket_service,
    station_provider,
    now_fn=None,
    on_search_activated=None,
) -> Application:
    """Build PTB Application with all handlers, without starting polling.

    `on_search_activated` is an optional async callback invoked after a search
    becomes ACTIVE (create/replace/restart) to let monitoring pick it up without
    requiring restart. Kept None in handler-only tests to keep isolation.
    """
    handlers = TelegramHandlers(
        ticket_service, station_provider, allowed_user_id, now_fn=now_fn, on_search_activated=on_search_activated
    )
    app = Application.builder().token(token).build()
    # Standalone commands
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("durum", handlers.durum))
    app.add_handler(CommandHandler("iptal", handlers.iptal))
    # Conversation for /ara wizard
    conv = handlers.build_conversation_handler()
    app.add_handler(conv)
    # Global restart callback – stale-safe, outside wizard user_data
    restart = RestartCallbackHandler(
        ticket_service, allowed_user_id, now_fn=now_fn, on_search_activated=on_search_activated
    )
    app.add_handler(CallbackQueryHandler(restart.handle, pattern=r"^restart:"))
    return app


def build_application_with_monitoring(
    token: str,
    allowed_user_id: int,
    ticket_service,
    station_provider,
    tcdd_client,
    notifier=None,
    monitoring_config=None,
    now_fn=None,
) -> tuple[Application, object | None]:
    """Build application plus monitoring service (without auto-starting loop).

    Returns (application, monitoring_service).
    MonitoringService is constructed with injected dependencies and remains idle
    until its polling loop is started explicitly. This keeps handler construction
    testable without starting worker. Runtime activation callback is injected
    into Telegram handlers so that newly created ACTIVE searches are picked up
    without requiring application restart.
    """
    from app.monitoring.config import load_monitoring_config
    from app.monitoring.notifier import TelegramNotifier
    from app.monitoring.service import MonitoringService

    cfg = monitoring_config or load_monitoring_config()

    # Prepare a temporary notifier for early MonitoringService construction
    # if real notifier requires app.bot (not yet built). Will be replaced
    # after app is built when possible.
    notifier_for_init = notifier
    if notifier_for_init is None:
        class _Noop:
            async def notify_found(self, *a, **kw):
                return None

            async def notify_expired(self, *a, **kw):
                return None

            async def notify_outage(self, *a, **kw):
                return None

            async def notify_auth_outage(self, *a, **kw):
                return None

            async def notify_recovery(self, *a, **kw):
                return None

        notifier_for_init = _Noop()

    # Build monitoring first so the activation callback can reference it
    monitoring = MonitoringService(
        ticket_service=ticket_service,
        tcdd_client=tcdd_client,
        notifier=notifier_for_init,
        config=cfg,
        now_fn=now_fn,
    )

    async def _on_search_activated(search_id: int | None = None):
        try:
            await monitoring.activate_search(search_id)
        except Exception:
            pass

    app = build_application(
        token, allowed_user_id, ticket_service, station_provider, now_fn=now_fn, on_search_activated=_on_search_activated
    )

    # If caller didn't supply a notifier, try to upgrade to real TelegramNotifier now that app.bot exists
    if notifier is None:
        try:
            bot = app.bot
        except Exception:
            bot = None
        if bot is not None:
            try:
                monitoring.notifier = TelegramNotifier(bot, allowed_user_id)
            except Exception:
                pass
    # Attach to app for lifecycle access if needed (use bot_data to avoid slot restrictions)
    try:
        app.bot_data["monitoring_service"] = monitoring  # type: ignore[attr-defined]
    except Exception:
        # Fallback if bot_data unavailable in test context
        try:
            object.__setattr__(app, "monitoring_service", monitoring)  # type: ignore
        except Exception:
            pass

    # Explicit lifecycle hooks: startup recovery resumes ACTIVE polling and FOUND retry
    # without auto-starting during plain handler construction (tests remain isolated).
    async def _monitoring_post_init(application):
        try:
            await monitoring.startup_recovery()
        except Exception:
            pass

    async def _monitoring_post_shutdown(application):
        try:
            await monitoring.shutdown()
        except Exception:
            pass

    # Register hooks using PTB post_init/post_shutdown if supported; keep explicit attribute for tests
    try:
        # PTB Application supports assignment post-build
        app.post_init = _monitoring_post_init  # type: ignore
        app.post_shutdown = _monitoring_post_shutdown  # type: ignore
    except Exception:
        pass

    # Also store explicit startup hook for direct invocation in tests
    try:
        app.bot_data["monitoring_post_init"] = _monitoring_post_init  # type: ignore
        app.bot_data["monitoring_post_shutdown"] = _monitoring_post_shutdown  # type: ignore
    except Exception:
        pass

    return app, monitoring


def create_handlers(ticket_service, station_provider, allowed_user_id: int, now_fn=None, on_search_activated=None) -> TelegramHandlers:
    """Helper to construct handlers without building Application (for tests)."""
    return TelegramHandlers(
        ticket_service, station_provider, allowed_user_id, now_fn=now_fn, on_search_activated=on_search_activated
    )
