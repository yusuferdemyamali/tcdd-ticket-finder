# TCDD Ticket Finder Bot

> Telegram üzerinden yönetilen, kişisel TCDD bilet takip botu. Belirlediğin rota ve saat aralığında **normal ekonomi koltuğu** açıldığında anında haber verir.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](./Dockerfile)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Nedir?

TCDD web sitesini 60-90 saniyede bir kontrol eder. Sadece **normal ekonomi** koltuk sayar — business veya erişilebilir koltukları uygun saymaz. Koltuk bulunduğunda tek bir Telegram mesajında tüm uygun seferleri listeler ve aramayı durdurur.

## Özellikler

- **Tek kullanıcı, tek aktif arama** — sade ve güvenli
- **Saat aralığı filtresi** — örn. 17:00–22:00 (inclusive)
- **Random polling 60–90s** — sabit interval yok
- **Tek mesajda tüm seferler** — spam yok
- **Restart-safe** — SQLite sayesinde container yeniden başlasa bile arama devam eder
- **Hata ayık** — TCDD kesintisini bir kez bildirir, spam yapmaz, düzelince haber verir

## Nasıl Çalışır?

```
/ara → Kalkış → Varış → Tarih → Saat Aralığı → Onay → ACTIVE
                                              ↓
                         TCDD 60-90s → Ekonomi >=1 ? → FOUND → Telegram → COMPLETED
                                              ↓ yok
                                         tekrar dene
```

`COMPLETED → "Bileti Alamadım" → ACTIVE` ile aynı arama tek tıkla yeniden başlatılır.

**State'ler:** `ACTIVE → FOUND → COMPLETED` · `ACTIVE → CANCELLED` · `ACTIVE → EXPIRED`

## Hızlı Başlangıç (Docker)

```bash
cp .env.example .env
# .env içini doldur: TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_ID, TCDD_TOKEN

docker compose up -d --build
docker compose logs -f
```

Durdur: `docker compose down` — veri `tcdd-data` volume'ünde kalır.

> `TCDD_TOKEN` süresi dolarsa `ebilet.tcddtasimacilik.gov.tr` JS bundle içinden yenileyin ve `.env`'i güncelleyin.

## Lokal Çalıştırma

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
cp .env.example .env  # DATABASE_PATH=data/tcdd-ticket.sqlite3 yap

python -m app.main
```

Spike doğrulama (gerçek TCDD API, Playwright yok):

```bash
python scripts/spike_tcdd.py --origin "Söğütlüçeşme" --destination "Ankara" --date 15.09.2026
```

## Telegram Kullanımı

| Komut | Ne yapar |
|-------|----------|
| `/start` | Ana menü |
| `/ara` | Yeni arama sihirbazı |
| `/durum` | Aktif aramayı göster |
| `/iptal` | Aktif aramayı iptal et |

**Akış:** `🚉 Nereden? → 🚉 Nereye? → 📅 Tarih (DD.MM.YYYY) → 🕐 En erken → 🕐 En geç → ✅ Onayla`

Tarih geçmiş olamaz, saat aralığı gece yarısını geçemez (`23:00→02:00` geçersiz).

Bildirim örneği:

```
🚨 UYGUN BİLET BULUNDU
Söğütlüçeşme → Ankara · 15 Eylül 2026

🚆 17:45 YHT · Ekonomi: 2 boş
🚆 19:05 YHT · Ekonomi: 1 boş

[TCDD'den Bilet Al]  [Bileti Alamadım — Tekrar Ara]
```

## Ortam Değişkenleri

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `TELEGRAM_BOT_TOKEN` | BotFather token | — |
| `TELEGRAM_ALLOWED_USER_ID` | Tek yetkili kullanıcı ID | — |
| `TCDD_TOKEN` | TCDD JWT (Authorization header) | — |
| `DATABASE_PATH` | SQLite yolu | `data/tcdd-ticket.sqlite3` (Docker: `/data/tcdd-ticket.sqlite3`) |
| `POLL_MIN_SECONDS` | Min polling | `60` |
| `POLL_MAX_SECONDS` | Max polling | `90` |
| `LOG_LEVEL` | Log seviyesi | `INFO` |

## Proje Yapısı

```
app/
├── tcdd/          # TCDD API izolasyonu (client, parser, stations)
├── ticket_searches/ # Domain + SQLite repository
├── telegram/      # Bot, handler, validasyon
├── monitoring/    # Polling, filtreleme, bildirim
├── database.py    # SQLite init
└── main.py        # Entrypoint
scripts/spike_tcdd.py  # Gerçek API doğrulama
tests/            # Filtering, state, parser testleri
```

TCDD response formatı `app/tcdd/` dışına sızmaz.

## Geliştirme

```bash
pytest -q          # testler
pytest tests/test_spike_parser.py -v  # parser
```

Kod kuralları: gereksiz abstraction yok, handler'da SQL yok, state geçişleri service'te, secret loglanmaz.

## Notlar

- Bu proje TCDD'nin undocumented web API'sini kullanır. API değişirse sadece `app/tcdd/` etkilenir.
- Playwright MVP dışıdır.
- Otomatik bilet almaz, sadece izler ve bildirir.

---

<p align="center">Kişisel kullanım için. TCDD yoğunluğunu spam'lemeyin.</p>
