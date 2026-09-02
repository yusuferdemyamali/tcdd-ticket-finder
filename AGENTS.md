# AGENTS.md

## Proje

TCDD Ticket Finder Bot.

Python tabanlı, Telegram üzerinden yönetilen kişisel tren bileti takip uygulaması.

Ana amaç:

Kullanıcının belirlediği rota, tarih ve kalkış saat aralığında TCDD üzerinde **normal ekonomi koltuğu** bulunduğunda Telegram bildirimi göndermek.

## Teknoloji

* Python 3.12+
* python-telegram-bot
* httpx
* Gerekirse curl_cffi
* SQLite
* Docker
* Docker Compose

Playwright MVP kapsamında değildir.

## MVP Kuralları

* Tek kullanıcı
* Tek aktif arama
* Tek yolcu
* Tek yön
* Tek seyahat tarihi
* Kalkış saat aralığı filtresi
* Polling: random 60-90 saniye
* Yalnızca normal ekonomi koltuğu
* Business uygunluk sayılmaz
* Engelli/özel koltuk uygunluk sayılmaz
* Birden fazla uygun sefer varsa tek Telegram mesajında hepsi gösterilir
* Koltuk bulununca arama durur
* "Bileti Alamadım - Tekrar Ara" ile aynı arama yeniden başlatılabilir
* Restart sonrası aktif arama devam etmelidir

## Search State'leri

Yalnızca:

* ACTIVE
* FOUND
* COMPLETED
* CANCELLED
* EXPIRED

Temel akış:

ACTIVE -> FOUND -> COMPLETED

Ek geçişler:

ACTIVE -> CANCELLED
ACTIVE -> EXPIRED
COMPLETED -> ACTIVE

Kullanıcıya Telegram bildirimi başarıyla gönderilmeden search `COMPLETED` yapılmamalıdır.

## TCDD Entegrasyonu

TCDD web uygulamasının kullandığı undocumented HTTP API kullanılacaktır.

TCDD entegrasyonunu `app/tcdd/` altında izole tut.

TCDD response formatını:

* Telegram katmanına
* persistence katmanına
* search domain katmanına

doğrudan sızdırma.

İlk geliştirme adımı:

`scripts/spike_tcdd.py`

ile gerçek TCDD API entegrasyonunu doğrulamaktır.

API spike doğrulanmadan TCDD davranışı hakkında kesin varsayım yapma.

## Availability Invariant

Bir sefer yalnızca:

`normal economy availability >= 1`

ise uygun kabul edilir.

Şunlar uygunluk değildir:

* Business > 0, Economy = 0
* Accessible/engelli > 0, Economy = 0

Bu kuralı parser ve filtering testleriyle koru.

## Hata Semantiği

TCDD hatasını boş sonuç gibi değerlendirme.

Aşağıdakiler "koltuk yok" değildir:

* timeout
* network error
* authentication error
* rate limit
* HTTP 5xx
* invalid JSON
* beklenmeyen response

TCDD kesintisinde kullanıcıya bir kez uyarı gönder.

Kesinti boyunca aynı uyarıyı spam yapma.

Bağlantı düzelince recovery bildirimi gönder.

## Persistence

SQLite source of truth'tur.

Kritik state yalnızca process memory'de tutulmamalıdır.

Container/application restart sonrasında:

* ACTIVE -> polling devam
* FOUND -> notification retry
* diğer state'ler -> işlem yok

## Kodlama Kuralları

* Gereksiz kapsam genişletme yapma.
* İstenmeyen yeni özellik ekleme.
* Future-proofing gerekçesiyle abstraction ekleme.
* Gereksiz refactor yapma.
* Mevcut çalışan davranışları sebepsiz değiştirme.
* Generic repository, CQRS, event sourcing veya Unit of Work ekleme.
* Yeni dependency eklemeden önce gerçek ihtiyaç olduğunu doğrula.
* Telegram handler'larda doğrudan SQL yazma.
* Domain state geçişlerini service katmanından yap.
* Küçük ve anlaşılır fonksiyonları tercih et.
* Secret değerleri loglama veya repository'ye commit etme.

## Testler

Özellikle şu davranışları test et:

* Economy 0 -> uygun değil
* Economy >= 1 -> uygun
* Business var, Economy yok -> uygun değil
* Engelli koltuğu var, normal Economy yok -> uygun değil
* Saat başlangıç ve bitiş değerleri inclusive
* Yanlış tarih filtrelenir
* Birden fazla uygun seferin tamamı döner
* State transition'ları
* Restart/retry için kritik davranışlar
* Gerçek TCDD response fixture'larının parsing'i

## Çalışma Şekli

Bir task üzerinde çalışırken:

1. Önce ilgili mevcut kodu incele.
2. Repository davranışını doğrula.
3. Gereksiz dosyalara dokunma.
4. Minimum değişiklikle requirement'ı uygula.
5. Kritik davranışları test et.
6. İş sonunda ne değiştiğini ve neyin doğrulandığını kısa şekilde raporla.

Belirsiz bir noktada mevcut kod veya gerçek API üzerinden doğrulama yapılabiliyorsa varsayım üretme.
