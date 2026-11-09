# Veritabanı, Biletleme ve QR Kod Mimarisi (Üye 3 Rapor Dokümanı)

## 1. Veri Modeli ve ORM / SQL Şema Uyumu

Sistemde Üye 2 tarafından geliştirilen `Hall`, `Seat` ve `SeatLock` modelleri korunmuş; ortak `Base` ve `SessionLocal` altyapısı üzerine `Event` ve `Ticket` modelleri eklenmiştir:

- **`Event` (`events` tablosu):**
  - `id` (`INTEGER`, PK, `ix_events_id`)
  - `hall_id` (`INTEGER`, `NOT NULL`, `FK -> halls.id`)
  - `name` (`VARCHAR(200)`, `NOT NULL`)
  - `starts_at` (`TIMESTAMPTZ`, `NOT NULL` — proje yol haritasındaki etkinlik tarihi/saati alanına karşılık gelir)
- **`Ticket` (`tickets` tablosu):**
  - `id` (`INTEGER`, PK, `ix_tickets_id`)
  - `ticket_code` (`VARCHAR(64)`, `NOT NULL`, tekillik: `CREATE UNIQUE INDEX ix_tickets_ticket_code ON tickets (ticket_code)`)
  - `event_id` (`INTEGER`, `NOT NULL`, `FK -> events.id`)
  - `seat_id` (`INTEGER`, `NOT NULL`, `FK -> seats.id`)
  - `session_id` (`VARCHAR(100)`, `NOT NULL`)
  - `created_at` (`TIMESTAMPTZ`, `NOT NULL`, `server_default=func.now()`)
  - **Bileşik Tekillik Kısıtı (`uq_tickets_event_seat`):** `UNIQUE (event_id, seat_id)`

### ORM ve SQL Kurulum Yollarının Birebir Uyumu ve Şema Sınırı

- `Ticket.ticket_code` alanında SQLAlchemy `unique=True, index=True` tanımı PostgreSQL'de `ix_tickets_ticket_code` adında tek bir `UNIQUE INDEX` üretir. SQL dosyalarında (`001_create_events_tickets.sql` ve `current_schema.sql`) hem sütun içi `UNIQUE` kısıtı hem de ayrı `CREATE UNIQUE INDEX` oluşturulması mükerrer indeks yaratacağından, SQL dosyaları da ORM ile birebir aynı şekilde yalnızca `ix_tickets_ticket_code` unique index'ini oluşturacak biçimde hizalanmıştır.
- Mevcut `Seat.status` alanında varsayılan değer (`default=SeatStatus.AVAILABLE`) ORM (Python) katmanında tanımlıdır; PostgreSQL'de sütun üzerinde `SERVER DEFAULT` bulunmaz. `current_schema.sql` dosyası mevcut `Seat` modelini değiştirmeden bu ORM davranışıyla birebir uyumlu hâle getirilmiştir.
- **Önemli Şema Notu:** Gerek `Base.metadata.create_all` gerekse `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` ifadeleri yalnızca mevcut olmayan tablo veya indeksleri oluşturur; daha önce farklı sütun, varsayılan değer veya kısıtlarla oluşturulmuş mevcut bir veritabanı şemasını otomatik olarak düzeltmez (`ALTER TABLE` yapmaz).

## 2. Etkinlik Seçimi ve İdempotent Seed Koruması

Mevcut satın alma uç noktasının (`POST /seats/{seat_id}/purchase`) istek gövdesi (`{"session_id": "..."}`) geriye dönük uyumluluk için değiştirilmemiştir. Satın alma sırasında koltuğun bağlı olduğu salona (`seat.hall_id`) ait etkinlik sorgulanır:

- Salona bağlı **hiç etkinlik yoksa (`0` kayıt)** veya **birden fazla etkinlik varsa (`>1` kayıt)** rastgele seçim yapılmaz; işlem `409 Conflict` ile reddedilir.
- `database/seed/001_main_hall_event_seed.sql` betiği `ORDER BY id LIMIT 1` gibi sessiz bir seçim yapmaz:
  - Hiç salon yoksa `Main Hall` salonunu, `A1`–`A6` koltuklarını ve `Opening Night Concert` etkinliğini oluşturur.
  - Tek ve uyumlu `Main Hall` salonu varsa mevcut koltukların ID, durum (`AVAILABLE`, `LOCKED`, `SOLD`), kilit ve biletlerini koruyarak yalnızca eksik kayıtları tamamlar.
  - Birden fazla salon/etkinlik veya prototiple uyumsuz mevcut bir salon/etkinlik durumu varsa transaction içinde `RAISE EXCEPTION` ile açık hata verir ve hiçbir değişikliği kalıcılaştırmaz.

## 3. Atomik Satın Alma, Eşzamanlılık ve `IntegrityError` Ayrımı

`purchase_seat` fonksiyonu aşağıdaki adımları **tek bir veritabanı transaction'ı** içinde yürütür:

1. **Satır Kilitleme (`SELECT ... FOR UPDATE`):** Koltuk kaydı `db.query(Seat).filter(Seat.id == seat_id).with_for_update().first()` ile sorgulanır.
2. **Durum ve Kilit Doğrulaması:** Koltuk mevcut değilse `404`, zaten `SOLD` ise `409`, ilgili `session_id` adına aktif `SeatLock` yoksa `409` döndürülür ve açıkça `db.rollback()` çalıştırılır.
3. **Bilet Oluşturma ve Kesin `IntegrityError` Sınıflandırması:**
   - `secrets.token_urlsafe(16)` ile rastgele `ticket_code` üretilir; veritabanı düzeyinde tekillik garantisi `ix_tickets_ticket_code` unique index'i ile sağlanır.
   - Kayıt ekleme işlemi `SAVEPOINT` (`db.begin_nested()`) içinde yapılır.
   - Hata sınıflandırması hata mesajı metninde kelime araması yapmaz; doğrudan PostgreSQL sürücüsünün (`psycopg2`) sağladığı `orig.pgcode` (`SQLSTATE`) ve `orig.diag.constraint_name` alanlarını kontrol eder:
     - `pgcode == "23505"` (`unique_violation`) ve `constraint_name == "uq_tickets_event_seat"` ise işlem `409 Conflict ("Ticket already exists for this event and seat")` ile reddedilir.
     - `pgcode == "23505"` ve `constraint_name` tanınan bilet kodu tekillik indeks/kısıt adlarından biri (`ix_tickets_ticket_code`, `uq_tickets_ticket_code`, `tickets_ticket_code_key`) ise sınırlı sayıda (`MAX_TICKET_CODE_RETRIES = 5`) yeni kod üretilerek tekrar denenir.
     - Diğer tüm `IntegrityError` türleri (ör. `23502` NOT NULL ihlali veya `23503` FK ihlali) kod çakışması sayılarak yeniden denenmez ve yanlış "bilet zaten var" mesajıyla maskelenmez; transaction `db.rollback()` ile geri alındıktan sonra hata dışarı aktarılır.
4. **Tek Commit:** `seat.status = SeatStatus.SOLD`, `db.delete(seat_lock)` ve `Ticket` kaydı tek bir `db.commit()` çağrısıyla kalıcı hâle getirilir.
5. **WebSocket Yayını:** Yalnızca `db.commit()` başarılı olduktan sonra bağlı istemcilere mevcut sözleşme formatında (`{"seat_id": seat_id, "status": "SOLD"}`) mesaj yayınlanır.

## 4. QR Kod Üretimi ve Doğrulama Yöntemi

- QR kod yalnızca `ticket_code` metnini içerir.
- Görsel veritabanında tutulmaz; `GET /tickets/{ticket_code}/qr` çağrıldığında `segno.make_qr(ticket_code)` ile bellek içinde (`io.BytesIO`, `scale=6`, `border=4`) `image/png` olarak anlık üretilir.
- QR üretimi satın alma transaction'ının dışındadır.
- **Doğrulama Yöntemi:**
  - Otomatik testte (`test_get_ticket_and_qr_endpoints_and_404`) dönen PNG baytlarının imzası, boyutları ve açılan IDAT piksel matrisi, aynı `segno.make_qr(ticket_code)` çıktısının modül matrisiyle karşılaştırılmaktadır (bu test bağımsız bir üçüncü parti QR decoder testi değildir).
  - Gerçek QR okuma doğrulaması **manuel kabul kontrolü** olarak yapılmıştır: Demo veritabanında oluşturulan biletin (`ticket_code = PBVG1sWVG7YgwHdKgBM94w`) `/tickets/PBVG1sWVG7YgwHdKgBM94w/qr` uç noktasından üretilen QR görseli telefon kamerasıyla okutulmuş ve `ticket_code` eşleşmesi doğrulanmıştır.

## 5. Doğrulama Test Kapsamı Özeti

- **Bilet Kodu Tekilliği:** Rastgele kod üretim testi yalnızca biçim ve örneklem kontrolü sağlar; gerçek tekillik garantisi veritabanındaki `ix_tickets_ticket_code` unique index'i ve zorlanmış çakışma/retry testleriyle (`test_ticket_code_collision_retries_and_succeeds`, `test_rollback_when_ticket_creation_fails_preserves_lock_and_status`) doğrulanmaktadır.
- **Servis Katmanında Eşzamanlı Satın Alma Testi:** `test_concurrent_purchase_requests_serialized` testi iki ayrı HTTP isteği yerine iki bağımsız SQLAlchemy `Session` üzerinden `purchase_seat` servis fonksiyonunu eşzamanlı çağırarak `SELECT ... FOR UPDATE` satır kilidinin davranışını doğrulamaktadır.

## 6. Frontend (Üye 1) Entegrasyon Rehberi

Frontend tüm çağrıları yapılandırılan `BACKEND_BASE_URL` (ör. yerel ortamda `http://127.0.0.1:8001`) üzerinden yapmalıdır:

1. **Satın Alma (`POST {BACKEND_BASE_URL}/seats/{seat_id}/purchase`):**
   - İstek gövdesi: `{"session_id": "user-a"}`
   - Yanıt (`200 OK`):
     ```json
     {
       "message": "Seat purchased successfully",
       "seat_id": 5,
       "status": "SOLD",
       "ticket_code": "PBVG1sWVG7YgwHdKgBM94w"
     }
     ```
2. **Bilet Detayı (`GET {BACKEND_BASE_URL}/tickets/{ticket_code}`):**
   - İçsel `session_id` alanı bu yanıtta dışarıya açılmaz.
3. **QR Görseli (`GET {BACKEND_BASE_URL}/tickets/{ticket_code}/qr`):**
   - `image/png` döner (`<img src={`${BACKEND_BASE_URL}/tickets/${ticketCode}/qr`} alt="Ticket QR" />`).

### CORS ve Güvenlik Notları

- **CORS Gereksinimi:** Mevcut `app/main.py` içinde `CORSMiddleware` tanımlı değildir ve mevcut uygulama yapılandırması bu görev kapsamında değiştirilmemiştir. Frontend farklı bir port üzerinde çalıştığında tarayıcıdan yapılacak JSON istekleri için Üye 2 ile koordineli olarak `CORSMiddleware` eklenmesi veya geliştirme sunucusunda proxy kullanılması gerekir.
- **Yetkilendirme Sınırı:** `ticket_code` benzersiz bir bilet tanımlayıcısıdır; bir kullanıcı kimlik doğrulama (authentication) mekanizması değildir.

## 7. Değiştirilen Ortak Dosyalar Listesi

| Dosya | Yapılan Değişiklik |
|---|---|
| ` README.md` | `backend/README.md` kurulum rehberine bağlantı eklendi |
| `backend/app/models/__init__.py` | `Event` ve `Ticket` modelleri dışa aktarıldı |
| `backend/app/services/seat_lock_service.py` | Yalnızca `purchase_seat` fonksiyonuna `with_for_update()`, atomik `Ticket` üretimi ve açık `db.rollback()` eklendi; `lock_seat` ve `release_seat` değiştirilmedi |
| `backend/app/main.py` | `tickets_router` ve `Event`/`Ticket` modelleri eklendi |
