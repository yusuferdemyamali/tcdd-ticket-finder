from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from .callbacks import RestartCallbackHandler
from .handlers import TelegramHandlers


def build_application(token: str, allowed_user_id: int, ticket_service, station_provider, now_fn=None) -> Application:
    """Build PTB Application with all handlers, without starting polling."""
    handlers = TelegramHandlers(ticket_service, station_provider, allowed_user_id, now_fn=now_fn)
    app = Application.builder().token(token).build()
    # Standalone commands
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("durum", handlers.durum))
    app.add_handler(CommandHandler("iptal", handlers.iptal))
    # Conversation for /ara wizard
    conv = handlers.build_conversation_handler()
    app.add_handler(conv)
    # Global restart callback – stale-safe, outside wizard user_data
    restart = RestartCallbackHandler(ticket_service, allowed_user_id, now_fn=now_fn)
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
    testable without starting worker.
    """
    from app.monitoring.config import load_monitoring_config
    from app.monitoring.notifier import TelegramNotifier
    from app.monitoring.service import MonitoringService

    app = build_application(token, allowed_user_id, ticket_service, station_provider, now_fn=now_fn)

    cfg = monitoring_config or load_monitoring_config()

    # If notifier not supplied, create one using app.bot and allowed_user_id
    if notifier is None:
        # app.bot is available after build (not yet running, but Bot instance exists)
        try:
            bot = app.bot
        except Exception:
            bot = None
        if bot is not None:
            notifier = TelegramNotifier(bot, allowed_user_id)
        else:
            # Fallback noop for tests
            class _Noop:
                async def notify_found(self, *a, **kw):
                    return None

                async def notify_expired(self, *a, **kw):
                    return None

            notifier = _Noop()

    monitoring = MonitoringService(
        ticket_service=ticket_service,
        tcdd_client=tcdd_client,
        notifier=notifier,
        config=cfg,
        now_fn=now_fn,
    )
    # Attach to app for lifecycle access if needed (use bot_data to avoid slot restrictions)
    try:
        app.bot_data["monitoring_service"] = monitoring  # type: ignore[attr-defined]
    except Exception:
        # Fallback if bot_data unavailable in test context
        try:
            object.__setattr__(app, "monitoring_service", monitoring)  # type: ignore
        except Exception:
            pass
    return app, monitoring


def create_handlers(ticket_service, station_provider, allowed_user_id: int, now_fn=None) -> TelegramHandlers:
    """Helper to construct handlers without building Application (for tests)."""
    return TelegramHandlers(ticket_service, station_provider, allowed_user_id, now_fn=now_fn)
