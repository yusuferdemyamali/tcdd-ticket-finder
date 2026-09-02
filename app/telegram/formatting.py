from __future__ import annotations

from app.ticket_searches.models import TicketSearch

from .validators import format_display_date


def format_search_summary(search: TicketSearch, include_status: bool = True) -> str:
    """Format active search summary for /durum and replacement prompts."""
    dep_date_display = format_display_date(search.travel_date)
    route = f"{search.origin_station_name} → {search.destination_station_name}"
    time_range = f"{search.departure_time_from} – {search.departure_time_to}"
    lines = [
        "📋 Mevcut bilet araması" if include_status else "🔎 Bilet araması",
        "",
        f"🚉 {route}",
        f"📅 {dep_date_display}",
        f"🕐 {time_range}",
        "👤 1 yolcu",
        "💺 Sadece ekonomi",
    ]
    if include_status:
        # Use ACTIVE display; other statuses not expected for active but include
        status_display = search.status.value if hasattr(search.status, "value") else str(search.status)
        # Turkish mapping
        mapping = {
            "ACTIVE": "Aktif",
            "FOUND": "Bulundu",
            "COMPLETED": "Tamamlandı",
            "CANCELLED": "İptal edildi",
            "EXPIRED": "Süresi doldu",
        }
        tr_status = mapping.get(status_display, status_display)
        lines.append(f"🔄 Durum: {tr_status}")
    return "\n".join(lines)


def format_durum_message(search: TicketSearch | None) -> str:
    if search is None:
        return "📋 Aktif bir bilet araman yok.\n\n/ara ile yeni bir arama başlatabilirsin."
    return format_search_summary(search, include_status=True)


def format_confirmation_message(
    origin_name: str,
    destination_name: str,
    travel_date_domain: str,
    time_from: str,
    time_to: str,
) -> str:
    """Format confirmation summary before creating search."""
    dep_date_display = format_display_date(travel_date_domain)
    time_range = f"{time_from} – {time_to}"
    lines = [
        "🔎 Bilet araması",
        "",
        f"🚉 {origin_name} → {destination_name}",
        f"📅 {dep_date_display}",
        f"🕐 {time_range}",
        "👤 1 yolcu",
        "💺 Sadece ekonomi",
        "",
        "TCDD 60–90 saniyelik aralıklarla kontrol edilecek.",
    ]
    return "\n".join(lines)


def format_start_message() -> str:
    return (
        "👋 Merhaba! TCDD bilet takip botuna hoş geldin.\n\n"
        "🔎 /ara — Yeni bilet araması başlat\n"
        "📋 /durum — Mevcut aramayı görüntüle\n"
        "❌ /iptal — Aktif aramayı iptal et"
    )


def format_no_active_for_cancel() -> str:
    return "📋 İptal edilecek aktif bir araman yok."


def format_cancel_success() -> str:
    return "✅ Aktif bilet araman iptal edildi."


def format_search_started() -> str:
    return "✅ Bilet araman başlatıldı. TCDD 60–90 saniyelik aralıklarla kontrol edilecek."


def format_replacement_started() -> str:
    return "✅ Bilet araman güncellendi. Yeni kriterlerle arama başlatıldı."


def format_operation_cancelled() -> str:
    return "❌ İşlem iptal edildi."


def format_wizard_cancelled_preserved() -> str:
    return "❌ İşlem iptal edildi. Mevcut araman aktif kalmaya devam ediyor."


def format_active_exists_message(search: TicketSearch) -> str:
    dep_date_display = format_display_date(search.travel_date)
    time_range = f"{search.departure_time_from}–{search.departure_time_to}"
    lines = [
        "⚠️ Zaten aktif bir bilet araman var.",
        "",
        f"🚉 {search.origin_station_name} → {search.destination_station_name}",
        f"📅 {dep_date_display}",
        f"🕐 {time_range}",
        "",
        "Yeni bir arama başlatırsan mevcut arama iptal edilecek.",
    ]
    return "\n".join(lines)


def format_stale_callback() -> str:
    return "⚠️ Bu işlem artık geçerli değil. Lütfen /ara ile yeni bir arama başlatın."


def format_unauthorized() -> str:
    return "⛔ Yetkisiz kullanıcı."


def format_found_tickets_message(search: TicketSearch, trains) -> str:
    """Format found-ticket notification with all eligible trains in one message.

    Includes route, travel date, train name/number, departure time, economy count.
    """
    dep_date_display = format_display_date(search.travel_date)
    route = f"{search.origin_station_name} → {search.destination_station_name}"
    lines = [
        "🎫 Bilet bulundu!",
        "",
        f"🚉 {route}",
        f"📅 {dep_date_display}",
        f"🕐 {search.departure_time_from} – {search.departure_time_to}",
        "",
        f"Bulunan seferler ({len(trains)}):",
    ]
    for t in trains:
        # Use train_name if available, fallback to train_number, fallback to id
        name = t.train_name or t.train_number or str(t.train_id)
        # Include number if different from name
        if t.train_number and t.train_number not in name:
            display_name = f"{name} ({t.train_number})"
        else:
            display_name = name
        lines.append(f"• {display_name} — {t.departure_time} — Ekonomi: {t.economy_available}")
    lines.extend([
        "",
        "👤 1 yolcu • 💺 Sadece ekonomi",
    ])
    return "\n".join(lines)


def format_expired_message(search: TicketSearch) -> str:
    """Format expiration notification for ended active search."""
    dep_date_display = format_display_date(search.travel_date)
    route = f"{search.origin_station_name} → {search.destination_station_name}"
    time_range = f"{search.departure_time_from} – {search.departure_time_to}"
    lines = [
        "⏰ Arama süresi doldu.",
        "",
        f"🚉 {route}",
        f"📅 {dep_date_display}",
        f"🕐 {time_range}",
        "",
        "Seyahat penceresi geçtiği için aktif araman sonlandırıldı.",
        "Yeni bir arama başlatmak için /ara kullanabilirsin.",
    ]
    return "\n".join(lines)


def format_restart_success() -> str:
    return "✅ Arama yeniden başlatıldı. TCDD 60–90 saniyelik aralıklarla kontrol edilecek."


def build_found_keyboard(search_id: int):
    """Build InlineKeyboard for found ticket: TCDD link + restart callback."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    # TCDD purchase URL – generic; route-aware deep linking can be added later
    tcdd_url = "https://ebilet.tcddtasimacilik.gov.tr/"
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("TCDD'den Bilet Al", url=tcdd_url)],
            [InlineKeyboardButton("Bileti Alamadım - Tekrar Ara", callback_data=f"restart:{search_id}")],
        ]
    )
    return keyboard
