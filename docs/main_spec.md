# TCDD Ticket Finder Bot — MainSpec

## 1. Amaç

Python tabanlı, Telegram üzerinden yönetilen kişisel bir tren bileti takip uygulaması geliştirilecektir.

Kullanıcı Telegram bot üzerinden:

* kalkış istasyonunu,
* varış istasyonunu,
* seyahat tarihini,
* kalkış saat aralığını

belirleyecektir.

Uygulama TCDD sistemini belirli aralıklarla kontrol edecek ve belirtilen kriterlerde **normal ekonomi sınıfında en az 1 uygun koltuk** bulunduğunda kullanıcıya Telegram üzerinden bildirim gönderecektir.

MVP yalnızca tek kullanıcı, tek yolcu ve aynı anda tek aktif arama destekleyecektir.

---

# 2. MVP Kapsamı

MVP aşağıdaki özellikleri desteklemelidir.

### Kullanıcı

* Sistem yalnızca tek Telegram kullanıcısı tarafından kullanılacaktır.
* Yetkili Telegram kullanıcı ID'si environment variable üzerinden tanımlanacaktır.
* Yetkisiz kullanıcılar bot fonksiyonlarını kullanamamalıdır.

### Arama

Bir arama aşağıdaki bilgileri içermelidir:

* Kalkış istasyonu
* Varış istasyonu
* Seyahat tarihi
* En erken kalkış saati
* En geç kalkış saati

Sabit domain kuralları:

* Yolcu sayısı: `1`
* Yön: tek yön
* Sınıf: yalnızca normal ekonomi
* Aynı anda aktif arama sayısı: `1`

---

# 3. MVP Dışı Kapsam

Aşağıdaki özellikler MVP kapsamında uygulanmayacaktır:

* Otomatik bilet satın alma
* TCDD hesabına login olma
* Ödeme işlemleri
* Koltuk seçimi
* Business sınıfı takibi
* Engelli koltuğu takibi
* Birden fazla yolcu
* Aynı anda birden fazla aktif arama
* Gidiş-dönüş
* Aktarmalı rota optimizasyonu
* Web panel
* Mobil uygulama
* Natural-language tarih parsing
* "yarın", "cumartesi", "akşam" gibi serbest zaman ifadeleri
* Kullanıcı sistemi / multi-user yapı
* Playwright entegrasyonu
* Otomatik TCDD token üretme veya yenileme

Bu özellikler MVP geliştirilirken kapsam genişletme gerekçesiyle eklenmemelidir.

---

# 4. Teknoloji Stack'i

## Runtime

* Python 3.12+

## Telegram

* `python-telegram-bot`

## HTTP / TCDD

İlk tercih:

* `httpx`

TCDD tarafında TLS fingerprint veya benzeri teknik bir engel oluşursa:

* `curl_cffi`

kullanılabilir.

`curl_cffi` başlangıçtan itibaren zorunlu dependency olmamalıdır.

## Persistence

* SQLite

## Scheduling

* Uygulama içinde çalışan lightweight scheduler
* Gerekirse APScheduler kullanılabilir.

## Configuration

* Environment variables
* `.env` desteği

## Deployment

* Docker
* Docker Compose

---

# 5. Kritik Teknik Karar: TCDD Entegrasyonu

TCDD entegrasyonu Playwright ile yapılmayacaktır.

Uygulama öncelikli olarak TCDD web uygulamasının kullandığı HTTP API üzerinden çalışacaktır.

Bu API:

* resmî public API olarak kabul edilmemeli,
* undocumented/private entegrasyon olarak değerlendirilmelidir.

Bu nedenle TCDD entegrasyonu uygulamanın geri kalanından tamamen izole edilmelidir.

TCDD API response formatı değiştiğinde Telegram, scheduler veya domain servislerinde değişiklik yapılması gerekmemelidir.

---

# 6. TCDD API Spike

Ana uygulama geliştirilmeden önce izole bir API spike yapılmalıdır.

Dosya:

`/scripts/spike_tcdd.py`

Spike'ın amacı:

> Playwright kullanmadan TCDD'den gerçek sefer ve ekonomi müsaitlik bilgisinin güvenilir biçimde alınabildiğini kanıtlamak.

Örnek hardcoded sorgu kullanılabilir:

* Söğütlüçeşme
* Ankara
* gelecekte geçerli bir seyahat tarihi

Spike aşağıdaki bilgileri terminale basmalıdır:

* tren/sefer ID
* tren adı/türü
* kalkış zamanı
* varış zamanı
* normal ekonomi müsaitlik sayısı

Örnek:

```text
18:20 YHT
Ekonomi: 0

19:05 YHT
Ekonomi: 3

21:10 YHT
Ekonomi: 1
```

## Spike Acceptance Criteria

Spike başarılı kabul edilmek için:

1. Playwright olmadan TCDD'ye istek atabilmelidir.
2. Kalkış ve varış istasyonları çözülebilmelidir.
3. İstenen tarihteki seferler alınabilmelidir.
4. Kalkış zamanı doğru parse edilmelidir.
5. Normal ekonomi cabin bilgisi diğer cabin türlerinden ayrılabilmelidir.
6. Business koltukları ekonomi olarak değerlendirilmemelidir.
7. Engelli/özel erişilebilir koltuklar normal ekonomi olarak değerlendirilmemelidir.
8. Ekonomi için kullanılabilir koltuk sayısı elde edilebilmelidir.
9. API hatası ile "sefer/koltuk bulunamadı" sonucu birbirinden ayrılabilmelidir.
10. Yanlış seyahat tarihine ait seferler filtrelenebilmelidir.

Spike başarısız olursa doğrudan Playwright implementasyonuna geçilmemelidir.

Önce problemin:

* authentication,
* token,
* header,
* TLS fingerprint,
* endpoint,
* request payload

kaynaklı olup olmadığı araştırılmalıdır.

---

# 7. Domain Invariant: Uygun Koltuk

Bir sefer yalnızca aşağıdaki şart gerçekleştiğinde AVAILABLE kabul edilir:

```text
normal economy availability >= 1
```

Aşağıdakiler uygunluk sağlamaz:

```text
Ekonomi = 0
Business = 5
```

Sonuç:

`NOT AVAILABLE`

---

```text
Ekonomi = 0
Engelli = 1
```

Sonuç:

`NOT AVAILABLE`

---

```text
Ekonomi = 0
Business = 3
Engelli = 1
```

Sonuç:

`NOT AVAILABLE`

---

```text
Normal Ekonomi = 1
```

Sonuç:

`AVAILABLE`

Bu kural TCDD parser testleriyle doğrulanmalıdır.

---

# 8. İstasyon Çözümleme

Kullanıcı Telegram üzerinden istasyon adını serbest metin olarak yazacaktır.

Örnek:

```text
söğüt
```

Sistem bunu TCDD canonical istasyon kaydına resolve edecektir.

Örneğin:

```text
İSTANBUL(SÖĞÜTLÜÇEŞME)
```

Tek eşleşme varsa otomatik seçilebilir.

Birden fazla eşleşme varsa Telegram inline keyboard ile kullanıcıya seçim yaptırılmalıdır.

Örneğin:

```text
İstanbul
```

sonucunda:

* Halkalı
* Bakırköy
* Söğütlüçeşme
* Bostancı
* Pendik

gibi eşleşmeler gösterilebilir.

İstasyon bilgisi mümkünse TCDD station datasından alınmalıdır.

Station datası her sorguda tekrar indirilmemeli, cache kullanılmalıdır.

Önerilen cache TTL:

`7 gün`

---

# 9. Telegram Kullanıcı Akışı

## `/start`

Ana menü gösterilir.

Minimum aksiyonlar:

* 🔎 Bilet Ara
* 📋 Mevcut Arama

---

# 10. `/ara` Conversation Flow

Conversation sırası:

```text
ORIGIN
↓
DESTINATION
↓
DATE
↓
FROM_TIME
↓
TO_TIME
↓
CONFIRM
```

## Kalkış istasyonu

Bot:

```text
🚉 Nereden hareket edeceksin?

İstasyon adını yaz:
```

---

## Varış istasyonu

Bot:

```text
🚉 Nereye gideceksin?
```

---

## Tarih

Bot:

```text
📅 Seyahat tarihini yaz.

Örnek: 15.09.2026
```

Kabul edilen format:

```text
DD.MM.YYYY
```

Geçmiş tarih kabul edilmemelidir.

Natural language parsing yapılmamalıdır.

---

## Başlangıç saati

```text
🕐 En erken kalkış saati?

Örnek: 17:00
```

Format:

```text
HH:MM
```

---

## Bitiş saati

```text
🕐 En geç kalkış saati?

Örnek: 22:00
```

Kural:

```text
end_time >= start_time
```

MVP'de gece yarısını geçen aralık desteklenmemelidir.

Örneğin:

```text
23:00 → 02:00
```

geçersiz kabul edilmelidir.

---

# 11. Arama Confirmation

Örnek:

```text
🔎 Bilet araması

🚉 İstanbul(Söğütlüçeşme) → Ankara Gar
📅 15.09.2026
🕐 17:00 – 22:00
👤 1 yolcu
💺 Sadece ekonomi

TCDD 60–90 saniyelik aralıklarla kontrol edilecek.
```

Butonlar:

```text
✅ Aramayı Başlat
❌ Vazgeç
```

Arama yalnızca kullanıcı confirmation verdikten sonra oluşturulmalıdır.

---

# 12. Tek Aktif Arama Kuralı

Aynı anda yalnızca bir aktif arama olabilir.

Kullanıcı `/ara` çalıştırdığında mevcut aktif arama varsa:

```text
⚠️ Zaten aktif bir bilet araman var.

Söğütlüçeşme → Ankara
15.09.2026
17:00–22:00

Yeni bir arama başlatırsan mevcut arama iptal edilecek.

[Aramayı Değiştir]
[Vazgeç]
```

gösterilmelidir.

Önemli:

`Aramayı Değiştir` seçildiği anda eski arama iptal edilmemelidir.

Yeni search wizard tamamlanana kadar mevcut arama aktif kalmalıdır.

Yeni aramanın confirmation aşamasında kullanıcı:

```text
Aramayı Başlat
```

dediğinde atomik olarak:

```text
old ACTIVE → CANCELLED
new search → ACTIVE
```

yapılmalıdır.

Wizard sırasında kullanıcı vazgeçerse eski arama çalışmaya devam etmelidir.

---

# 13. Polling

Aktif arama TCDD üzerinde:

```text
60–90 saniye
```

arasında random interval ile kontrol edilmelidir.

Tam sabit interval kullanılmamalıdır.

Örneğin:

```text
67 sn
83 sn
61 sn
76 sn
89 sn
```

---

# 14. Polling Persistence

Arama kaydında:

* `last_checked_at`
* `next_check_at`

saklanmalıdır.

Container restart olduğunda aktif arama kaybolmamalıdır.

Boot sırasında:

```text
ACTIVE search var mı?
↓
evet
↓
next_check_at geçmiş mi?
↓
evet
↓
hemen sorgula
```

davranışı uygulanmalıdır.

Restart kullanıcının yeniden `/ara` çalıştırmasını gerektirmemelidir.

---

# 15. Saat Filtresi

Kullanıcının verdiği kalkış saat aralığı inclusive olmalıdır.

Örnek:

```text
17:00 – 22:00
```

Sonuç:

```text
17:00 ✅
17:01 ✅
21:59 ✅
22:00 ✅
22:01 ❌
```

Filtre yalnızca kalkış saatine uygulanır.

Varış saati MVP kapsamında kriter değildir.

---

# 16. Birden Fazla Uygun Sefer

Saat aralığında birden fazla uygun sefer varsa hepsi kullanıcıya bildirilmelidir.

Ancak her sefer için ayrı Telegram mesajı gönderilmemelidir.

Tek mesaj içerisinde tüm uygun seferler listelenmelidir.

Örnek:

```text
🚨 UYGUN BİLET BULUNDU

Söğütlüçeşme → Ankara
15 Eylül 2026

🚆 17:45 YHT
💺 Ekonomi: 2 boş koltuk

🚆 19:05 YHT
💺 Ekonomi: 1 boş koltuk

🚆 21:10 YHT
💺 Ekonomi: 6 boş koltuk

Arama durduruldu.
```

Butonlar:

```text
TCDD'den Bilet Al
Bileti Alamadım — Tekrar Ara
```

---

# 17. Koltuk Bulunduktan Sonraki Davranış

Koltuk bulunduğu anda polling durmalıdır.

Search state:

```text
ACTIVE
↓
FOUND
```

olmalıdır.

Telegram bildirimi başarıyla gönderildikten sonra:

```text
FOUND
↓
COMPLETED
```

olmalıdır.

Kullanıcı bileti başarıyla aldıysa hiçbir şey yapmasına gerek yoktur.

Arama `COMPLETED` kalır.

---

# 18. "Bileti Alamadım — Tekrar Ara"

Bildirim mesajında:

```text
Bileti Alamadım — Tekrar Ara
```

butonu bulunmalıdır.

Buton callback'i search ID içermelidir.

Örneğin:

```text
restart_search:42
```

Böylece eski Telegram mesajları yanlış aramayı yeniden başlatamaz.

Callback çalıştırıldığında:

1. Search bulunmalıdır.
2. Search `COMPLETED` durumda olmalıdır.
3. Seyahat zamanı henüz geçmemiş olmalıdır.

Uygunsa:

```text
COMPLETED
↓
ACTIVE
```

yapılmalıdır.

`next_check_at` yakın geleceğe veya immediate check'e ayarlanabilir.

Seyahat zamanı geçmişse arama yeniden başlatılmamalıdır.

Kullanıcıya:

```text
❌ Bu aramanın seyahat zamanı geçtiği için yeniden başlatılamıyor.
```

mesajı gösterilmelidir.

---

# 19. Search State Machine

Geçerli search state'leri:

```text
ACTIVE
FOUND
COMPLETED
CANCELLED
EXPIRED
```

State machine:

```text
ACTIVE
  │
  ├── kullanıcı iptal eder
  │        ↓
  │    CANCELLED
  │
  ├── saat aralığı geçer
  │        ↓
  │     EXPIRED
  │
  └── ekonomi koltuğu bulunur
           ↓
         FOUND
           │
           │ Telegram notification başarılı
           ↓
       COMPLETED
           │
           │ Bileti alamadım
           ↓
         ACTIVE
```

Geçersiz state transition yapılmamalıdır.

---

# 20. Notification Reliability Invariant

En kritik reliability kurallarından biri:

> Kullanıcıya başarılı Telegram bildirimi gönderilmeden search `COMPLETED` kabul edilmemelidir.

Yanlış:

```text
koltuk bulundu
↓
COMPLETED
↓
process crash
↓
Telegram gönderilemedi
```

Doğru:

```text
koltuk bulundu
↓
FOUND
↓
Telegram gönder
↓
başarılı
↓
COMPLETED
```

Telegram gönderimi başarısız olursa:

```text
FOUND
```

olarak kalmalıdır.

Sonraki worker/restart sırasında notification yeniden denenmelidir.

---

# 21. Restart Recovery

Application başlangıcında search state kontrol edilmelidir.

### ACTIVE

Polling devam ettirilir.

### FOUND

Telegram notification yeniden denenir.

### COMPLETED

İşlem yapılmaz.

### CANCELLED

İşlem yapılmaz.

### EXPIRED

İşlem yapılmaz.

Bu davranış container/application restart'larına dayanıklı olmalıdır.

---

# 22. Search Expiration

Seyahat günü belirlenen:

```text
departure_time_to
```

geçtiğinde aktif search otomatik `EXPIRED` olmalıdır.

Kullanıcıya tek sefer:

```text
⌛ Arama sona erdi.

Belirlediğin seyahat saat aralığı geçti ve uygun ekonomi koltuğu bulunamadı.
```

bildirimi gönderilebilir.

Expired search tekrar polling'e alınmamalıdır.

---

# 23. TCDD Hata Davranışı

TCDD sorgusu başarısız olduğunda sistem bunu:

```text
koltuk yok
```

olarak değerlendirmemelidir.

Örneğin aşağıdaki durumlar error'dır:

* timeout
* DNS/network failure
* HTTP 5xx
* authentication failure
* rate limit
* invalid JSON
* beklenmeyen response schema

TCDD client anlamlı exception tipleri üretmelidir.

Örneğin:

```text
TcddNetworkError
TcddAuthenticationError
TcddRateLimitError
TcddServerError
TcddInvalidResponseError
```

Telegram tarafında tüm teknik detayları kullanıcıya göstermek zorunlu değildir.

---

# 24. TCDD Kesinti Bildirimi

İlk TCDD hatasında Telegram üzerinden:

```text
⚠️ TCDD şu anda sorgulanamıyor.
Arka planda tekrar denemeye devam edeceğim.
```

mesajı gönderilmelidir.

Kesinti devam ederken her polling interval'ında tekrar bildirim gönderilmemelidir.

Örnek:

```text
başarılı
başarılı
hata → bildir
hata → sessiz
hata → sessiz
hata → sessiz
```

Bağlantı tekrar başarılı olduğunda:

```text
✅ TCDD bağlantısı yeniden kuruldu.
Bilet araması devam ediyor.
```

mesajı gönderilmelidir.

Sonra yeni bir bağımsız kesinti yaşanırsa tekrar hata bildirimi yapılabilir.

---

# 25. TCDD Authentication Hatası

TCDD authentication/token problemi normal network hatasından ayırt edilmelidir.

Tek kullanıcı ve bot sahibi aynı kişi olduğu için daha açıklayıcı mesaj gönderilebilir:

```text
⚠️ TCDD kimlik doğrulaması başarısız.

TCDD token bilgisinin yenilenmesi gerekebilir.
Bilet araması şu anda TCDD'yi sorgulayamıyor.
```

Token otomatik yenilenmeye çalışılmamalıdır.

MVP'de token `.env` üzerinden yönetilir.

---

# 26. Retry / Backoff

Normal polling:

```text
60–90 saniye
```

TCDD başarısız olduğunda basit backoff uygulanabilir.

Örneğin:

```text
ilk hata → 120 sn
ikinci hata → 240 sn
sonraki hatalar → max 300 sn
```

İlk başarılı TCDD response sonrasında polling tekrar:

```text
60–90 saniye
```

aralığına dönmelidir.

---

# 27. `/durum`

Komut mevcut aramayı göstermelidir.

Örnek:

```text
📋 Mevcut bilet araması

🚉 Söğütlüçeşme → Ankara
📅 15.09.2026
🕐 17:00 – 22:00
💺 Ekonomi
🔄 Durum: Aktif
🕐 Son başarılı kontrol: 16:42
```

Aktif arama yoksa açıkça belirtilmelidir.

---

# 28. `/iptal`

Aktif aramayı iptal eder.

State:

```text
ACTIVE → CANCELLED
```

Polling durmalıdır.

Kullanıcıya confirmation mesajı gönderilmelidir.

`FOUND`, `COMPLETED`, `EXPIRED` veya `CANCELLED` search yanlışlıkla tekrar cancel edilmemelidir.

---

# 29. Veri Modeli

SQLite tablosu:

## `ticket_searches`

Alanlar:

```text
id

origin_station_id
origin_station_name

destination_station_id
destination_station_name

travel_date

departure_time_from
departure_time_to

status

last_checked_at
last_successful_check_at
next_check_at

tcdd_outage_notified
last_tcdd_error_at

found_at
completed_at
cancelled_at
expired_at

created_at
updated_at
```

MVP'de:

* user tablosu gerekli değildir.
* passenger count tutulması zorunlu değildir.
* arama geçmişi ayrı tabloya bölünmemelidir.

---

# 30. Domain Modelleri

## Station

```python
@dataclass
class Station:
    id: int | str
    name: str
```

## TrainAvailability

```python
@dataclass
class TrainAvailability:
    train_id: str
    train_name: str
    departure_at: datetime
    arrival_at: datetime
    economy_available: int
```

Business availability gibi MVP'de kullanılmayan TCDD alanları domain modeline taşınmamalıdır.

---

# 31. TCDD Client

Sorumluluğu yalnızca TCDD entegrasyonudur.

Örnek interface:

```python
class TcddClient:

    async def get_stations(self) -> list[Station]:
        ...

    async def search_trains(
        self,
        origin_station_id,
        destination_station_id,
        travel_date,
    ) -> list[TrainAvailability]:
        ...
```

`TcddClient` aşağıdakileri bilmemelidir:

* Telegram
* SQLite
* aktif search
* polling interval
* search state machine

---

# 32. StationService

İstasyon aramasından sorumludur.

Örnek:

```python
class StationService:

    async def search(
        self,
        query: str,
    ) -> list[Station]:
        ...
```

Sorumluluklar:

* station cache
* text normalization
* prefix eşleşmesi
* substring eşleşmesi
* canonical station dönüşü

---

# 33. TicketSearchService

Domain kurallarının merkezi olmalıdır.

Örnek operasyonlar:

```text
create_search
get_active_search
get_search
cancel_search
replace_search
restart_search
mark_found
mark_completed
expire_search
```

Telegram handler doğrudan SQLite query çalıştırmamalıdır.

Search state geçişleri service üzerinden yapılmalıdır.

---

# 34. Repository

SQLite erişimi küçük bir repository ile izole edilmelidir.

Örneğin:

```python
class TicketSearchRepository:

    def create(...)
    def get_active(...)
    def get_by_id(...)
    def update(...)
```

Aşağıdaki soyutlamalar eklenmemelidir:

* GenericRepository
* BaseRepository
* UnitOfWork
* Domain Aggregate framework
* CQRS
* Event sourcing

MVP için bunlar gereksizdir.

---

# 35. Filtering

TCDD'den gelen seferlerin kullanıcı search kriterlerine uygunluğu ayrı fonksiyonda değerlendirilmelidir.

Örneğin:

```python
def filter_matching_trains(
    trains,
    travel_date,
    from_time,
    to_time,
):
    ...
```

Kurallar:

```text
departure date == travel_date

AND

departure time >= from_time

AND

departure time <= to_time

AND

economy_available >= 1
```

Sonuç kalkış saatine göre küçükten büyüğe sıralanmalıdır.

---

# 36. SearchWorker

Worker orkestrasyon katmanıdır.

Temel davranış:

```text
active search al

↓

expired mı?
→ evet → expire + bildir

↓

TCDD sorgula

↓

error?
→ TCDD hata state'ini işle

↓

TCDD yeniden çalışıyor mu?
→ recovery mesajı gönder

↓

kullanıcı kriterlerine göre filtrele

↓

uygun sefer var mı?

hayır
→ next_check_at oluştur

evet
→ FOUND
→ Telegram bildir
→ başarılıysa COMPLETED
```

Worker içerisinde Telegram conversation logic bulunmamalıdır.

---

# 37. Telegram Callback Güvenliği

Callback payload'ları ilgili search ID'sini içermelidir.

Örnek:

```text
restart_search:42
```

Callback çalıştırılırken mevcut database state yeniden doğrulanmalıdır.

Telegram mesajının eski olması callback'in otomatik olarak geçerli olduğu anlamına gelmemelidir.

---

# 38. Yetkilendirme

Environment variable:

```text
TELEGRAM_ALLOWED_USER_ID
```

kullanılmalıdır.

Her Telegram interaction öncesinde:

```text
effective_user.id == TELEGRAM_ALLOWED_USER_ID
```

kontrol edilmelidir.

Yetkisiz kullanıcı uygulama state'ini okuyamamalı veya değiştirememelidir.

---

# 39. Environment Variables

Minimum `.env.example`:

```text
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_ID=

TCDD_TOKEN=

DATABASE_PATH=data/app.db

POLL_MIN_SECONDS=60
POLL_MAX_SECONDS=90

LOG_LEVEL=INFO
```

Secrets repository'ye commit edilmemelidir.

---

# 40. Proje Yapısı

```text
tcdd-ticket-bot/
│
├── app/
│   ├── bot/
│   │   ├── handlers.py
│   │   ├── conversations.py
│   │   └── keyboards.py
│   │
│   ├── tcdd/
│   │   ├── client.py
│   │   ├── parser.py
│   │   ├── stations.py
│   │   ├── models.py
│   │   └── exceptions.py
│   │
│   ├── search/
│   │   ├── models.py
│   │   ├── repository.py
│   │   ├── service.py
│   │   ├── filtering.py
│   │   └── worker.py
│   │
│   ├── database.py
│   ├── config.py
│   └── main.py
│
├── tests/
│   ├── test_filtering.py
│   ├── test_search_service.py
│   └── test_tcdd_parser.py
│
├── scripts/
│   └── spike_tcdd.py
│
├── data/
│
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

Bu yapı MVP sırasında gereksiz yeni katmanlarla genişletilmemelidir.

---

# 41. Logging

Minimum olarak aşağıdakiler loglanmalıdır:

* application start
* application shutdown
* search oluşturuldu
* search iptal edildi
* search yeniden başlatıldı
* search expired oldu
* TCDD query başladı
* TCDD query başarılı
* TCDD query başarısız
* TCDD response parse hatası
* uygun sefer bulundu
* Telegram notification başarılı
* Telegram notification başarısız
* restart recovery işlemleri

Secret bilgiler loglanmamalıdır.

Özellikle:

```text
TELEGRAM_BOT_TOKEN
TCDD_TOKEN
```

hiçbir log çıktısında görünmemelidir.

---

# 42. Test Stratejisi

MVP için tüm kodu yüksek coverage'a zorlamak gerekli değildir.

Ancak kritik domain kuralları mutlaka test edilmelidir.

## Filtering Tests

* Ekonomi 0 → eşleşmez
* Ekonomi 1 → eşleşir
* Business >0 / Ekonomi 0 → eşleşmez
* Engelli >0 / normal ekonomi 0 → eşleşmez
* Saat aralığından önce → eşleşmez
* Saat aralığından sonra → eşleşmez
* Tam başlangıç saatinde → eşleşir
* Tam bitiş saatinde → eşleşir
* Yanlış seyahat tarihi → eşleşmez
* Birden fazla uygun sefer → tümü döner
* Sonuçlar kalkış saatine göre sıralanır

## State Machine Tests

* ACTIVE → FOUND
* FOUND → COMPLETED
* COMPLETED → ACTIVE
* ACTIVE → CANCELLED
* ACTIVE → EXPIRED
* expired search restart edilemez
* cancelled search restart callback'i ile yanlışlıkla aktive edilemez

## Parser Tests

Gerçek TCDD response fixture'ları kullanılmalıdır.

Özellikle:

* economy
* business
* accessibility
* empty availability
* malformed response

senaryoları test edilmelidir.

---

# 43. Temel Acceptance Criteria

MVP tamamlanmış sayılabilmesi için:

1. Yetkili kullanıcı Telegram botu kullanabilmelidir.
2. `/ara` üzerinden kalkış istasyonu seçilebilmelidir.
3. Varış istasyonu seçilebilmelidir.
4. Seyahat tarihi girilebilmelidir.
5. Kalkış saat aralığı girilebilmelidir.
6. Arama confirmation sonrası aktif olmalıdır.
7. TCDD 60–90 saniyelik random interval ile sorgulanmalıdır.
8. TCDD sorgusu application restart sonrasında otomatik devam etmelidir.
9. Sadece normal ekonomi koltuğu uygun kabul edilmelidir.
10. Business availability alarm oluşturmamalıdır.
11. Engelli/özel koltuk availability alarm oluşturmamalıdır.
12. Saat aralığındaki tüm uygun trenler bulunmalıdır.
13. Birden fazla uygun tren tek Telegram mesajında gösterilmelidir.
14. Bildirimden sonra polling durmalıdır.
15. Search ancak başarılı Telegram notification sonrasında COMPLETED olmalıdır.
16. `Bileti Alamadım — Tekrar Ara` aynı kriterlerle search'ü tekrar aktive etmelidir.
17. Geçmiş search tekrar aktive edilmemelidir.
18. `/durum` mevcut arama bilgilerini göstermelidir.
19. `/iptal` aktif aramayı durdurmalıdır.
20. Aktif arama varken yeni `/ara` mevcut search'ü doğrudan silmemelidir.
21. Yeni arama confirmation verilince eski search CANCELLED olmalıdır.
22. TCDD erişilemez olduğunda kullanıcı bir kez uyarılmalıdır.
23. Kesinti boyunca hata notification spam'i yapılmamalıdır.
24. TCDD tekrar erişilebilir olduğunda kullanıcı bilgilendirilmelidir.
25. Arama zaman aralığı geçtiğinde search EXPIRED olmalıdır.
26. SQLite içerisinde search state kalıcı olmalıdır.
27. Container restart state kaybına neden olmamalıdır.
28. TCDD API response formatı Telegram/domain katmanlarına sızmamalıdır.
29. Secrets repository veya log içerisinde bulunmamalıdır.
30. TCDD API spike Playwright kullanılmadan başarıyla tamamlanmalıdır.

---

# 44. Uygulama Sırası

Development aşağıdaki sırada yapılmalıdır.

## Phase 1 — TCDD Spike

Önce:

```text
scripts/spike_tcdd.py
```

tamamlanmalıdır.

API çalıştığı kanıtlanmadan Telegram bot geliştirmesine başlanmamalıdır.

---

## Phase 2 — TCDD Adapter

Implement:

```text
TcddClient
TcddParser
StationService
TrainAvailability
Tcdd exceptions
```

Parser unit testleri yazılmalıdır.

---

## Phase 3 — Persistence

Implement:

```text
SQLite init
ticket_searches
TicketSearchRepository
```

---

## Phase 4 — Domain

Implement:

```text
TicketSearchService
state transitions
filtering
expiration
```

Domain testleri yazılmalıdır.

---

## Phase 5 — Telegram

Implement:

```text
/start
/ara
/durum
/iptal

station selection
date/time conversation
confirmation
replace-search confirmation
```

---

## Phase 6 — Worker

Implement:

```text
60–90 sec polling
TCDD query
filter
FOUND
notification
COMPLETED
retry/backoff
outage detection
recovery notification
```

---

## Phase 7 — Recovery

Test:

```text
ACTIVE sırasında restart
FOUND sırasında restart
TCDD outage sırasında restart
```

State kaybı yaşanmamalıdır.

---

## Phase 8 — Docker

Implement:

```text
Dockerfile
docker-compose.yml
persistent SQLite volume
environment configuration
```

Container silinip yeniden oluşturulduğunda SQLite volume korunmalıdır.

---

# 45. Tasarım İlkeleri

Bu proje geliştirilirken aşağıdaki ilkeler korunmalıdır.

### Basitlik

MVP'yi çözmeyen abstraction eklenmemelidir.

### Deterministik domain

Telegram veya TCDD response detayları domain kurallarını belirlememelidir.

### TCDD izolasyonu

Undocumented API değişiklikleri mümkün olduğunca yalnızca `app/tcdd/` altında değişiklik gerektirmelidir.

### Restart safety

Process memory hiçbir kritik state için source of truth olmamalıdır.

### Notification reliability

Koltuk bulunduğu halde kullanıcının haberdar olmaması kabul edilemez bir hata sınıfıdır.

### Scope discipline

MVP geliştirilirken gelecekte lazım olabilir gerekçesiyle multi-user, web panel, otomatik satın alma veya Playwright eklenmemelidir.

---

# 46. MVP'nin Nihai Kullanıcı Senaryosu

```text
/start
↓
🔎 Bilet Ara

↓

Söğütlüçeşme

↓

Ankara

↓

15.09.2026

↓

17:00

↓

22:00

↓

✅ Aramayı Başlat
```

Application:

```text
ACTIVE

↓

60–90 saniye random

↓

TCDD API

↓

normal ekonomi yok

↓

tekrar sorgula

↓

normal ekonomi yok

↓

tekrar sorgula

↓

17:45 → 2 ekonomi
19:05 → 1 ekonomi
21:10 → 6 ekonomi

↓

FOUND

↓

Telegram
```

Kullanıcı:

```text
🚨 UYGUN BİLET BULUNDU

Söğütlüçeşme → Ankara
15.09.2026

🚆 17:45 YHT
💺 Ekonomi: 2

🚆 19:05 YHT
💺 Ekonomi: 1

🚆 21:10 YHT
💺 Ekonomi: 6

Arama durduruldu.

[TCDD'den Bilet Al]
[Bileti Alamadım — Tekrar Ara]
```

Telegram gönderimi başarılı:

```text
FOUND → COMPLETED
```

Kullanıcı bileti alırsa:

```text
işlem tamam
```

Kullanıcı bileti alamazsa:

```text
[Bileti Alamadım — Tekrar Ara]

↓

COMPLETED → ACTIVE

↓

polling yeniden başlar
```

Bu akış MVP'nin temel ürün sözleşmesidir.
