# Birinci Aşama (S1) Murat Gürel (Üye 3) Teslim Kaydı (M9)

## 1. Genel Teslim Özeti

- **Geliştirici:** Murat Gürel (Üye 3 — Veri Modeli, Migration, ER Diyagramı, Bilet, QR Check-in, PDF ve E-posta Teslim Altyapısı)
- **Çalışma Dalı (Branch):** `feature/s1-data-ticket`
- **Temel Sürüm (Baseline Commit):** `20a8cc8` (`main`)
- **Alembic Migration Sürümü:** `001_baseline` → `002_s1_schema` (`head`)
- **İzole Test Veritabanı:** `event_ticketing_test` (`postgresql+psycopg2://postgres:postgres@localhost:5432/event_ticketing_test`)

---

## 2. Görev Matrisi ve Tamamlanan Teslimler (`K0`, `M1`–`M9`)

| Görev Kodu | Teslim Edilen İş | İlgili Dosyalar | Durum |
|---|---|---|---|
| **K0** | Mevcut `cinema` veritabanı yedeği, geri yükleme komutu ve S1 veri taslağı | [s1-data-dictionary.md](s1-data-dictionary.md) | Tamamlandı |
| **M1** | Etkinlik bazlı S1 veri modeli (`Hall`, `SeatSegment`, `Seat`, `Event`, `TicketCategory`, `EventSeat`, `GuestSession`, `Reservation`, `ReservationItem`, `Order`, `Ticket`, `CheckIn`, `EmailDelivery`, `IdempotencyRecord`), ER diyagramı ve alan sözlüğü | `backend/app/models/*.py`, [er-diagram.md](../../database/diagrams/er-diagram.md), [current_schema.sql](../../database/schema/current_schema.sql) | Tamamlandı |
| **M2** | Eski biletleri (`PBVG1sWVG7YgwHdKgBM94w` vb.) ve satışları `EventSeat` (`SOLD`) + `Order` yapısına kayıpsız aktaran Alembic sıralı migration | [alembic.ini](../../backend/alembic.ini), [001_baseline_initial_schema.py](../../backend/alembic/versions/001_baseline_initial_schema.py), [002_s1_event_inventory_and_orders.py](../../backend/alembic/versions/002_s1_event_inventory_and_orders.py) | Tamamlandı |
| **M3** | 2 salon (`Main Hall` 40 koltuk + koridorlu 2 segment + A1 `orphan_exempt`; `Studio Hall` 24 koltuk + tek segment + A1 `orphan_exempt`) ve 3 etkinlikli (`Opening Night Concert`, `Symphony Gala Night`, `Indie Acoustic Session`) idempotent seed | [002_s1_two_halls_three_events_seed.sql](../../database/seed/002_s1_two_halls_three_events_seed.sql), [seed_service.py](../../backend/app/services/seed_service.py) | Tamamlandı |
| **M4** | Çoklu koltuk siparişinde her `ReservationItem` / `EventSeat` için `Order`'a bağlı benzersiz `Ticket` (`VALID`) üretimi, `SAVEPOINT` çakışma yeniden denemesi | [ticket_service.py](../../backend/app/services/ticket_service.py), [ticket.py (schema)](../../backend/app/schemas/ticket.py) | Tamamlandı |
| **M5** | `SELECT ... FOR UPDATE` ile atomik tek kullanımlık QR giriş doğrulaması (`VALID → USED` + `CheckIn` kaydı; `ACCEPTED`, `TICKET_ALREADY_USED`, `WRONG_EVENT`, `TICKET_NOT_FOUND`) | [checkin_service.py](../../backend/app/services/checkin_service.py), [checkin.py (schema)](../../backend/app/schemas/checkin.py) | Tamamlandı |
| **M6** | Siparişin tüm biletlerini ve QR kodlarını içeren, Türkçe Unicode font destekli PDF üretim servisi ve bağımsız OpenCV/`pypdf` QR çözümleme doğrulaması | [pdf_service.py](../../backend/app/services/pdf_service.py) | Tamamlandı |
| **M7** | `EmailDelivery` kalıcı iş tablosu, `FOR UPDATE SKIP LOCKED` ile 3 denemeli (`10s`, `30s` backoff) gönderici ve 60 sn `RATE_LIMITED` koruması | [email_service.py](../../backend/app/services/email_service.py), [email_delivery.py (schema)](../../backend/app/schemas/email_delivery.py) | Tamamlandı |
| **M8** | İzole PostgreSQL üzerinde `T02`, `T03`, `T14`, `T23`, `T24`, `T25`, `T27` testleri ve eşzamanlılık veri hazırlığı | [test_s1_murat_deliverables.py](../../backend/tests/test_s1_murat_deliverables.py) | Tamamlandı |
| **M9** | Veri sözlüğü ve Birinci Aşama Murat teslim kaydı | [s1-murat-delivery-record.md](s1-murat-delivery-record.md) | Tamamlandı |

---

## 3. Murat'ın Test Sonuç Tablosu (M8 — İzole `event_ticketing_test` Veritabanı)

Test çalıştırma komutu:
```powershell
Push-Location .\backend
try {
    $env:TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/event_ticketing_test"
    .\venv\Scripts\python.exe -m pytest -v
} finally {
    Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
    Pop-Location
}
```

| Test Kimliği | Test Fonksiyonu | Senaryo ve Doğrulanan Sonuç | Sonuç |
|---|---|---|---|
| **T02** | `test_t02_fresh_and_upgrade_migration_preserves_legacy_tickets` | `001_baseline` şemasındaki mevcut bilet (`PBVG1sWVG7YgwHdKgBM94w`), `002_s1_schema` yükseltmesi sonrasında `Order`, `Ticket(status='VALID', unit_price_kurus=50000)` ve `EventSeat(status='SOLD')` olarak kayıpsız korunur; diğer koltuklar `AVAILABLE` kalır | **PASS** |
| **T03** | `test_t03_same_hall_two_events_independent_seat_occupancy` | `Main Hall` salonundaki iki ayrı etkinlikte (`Opening Night Concert` ve `Symphony Gala Night`) fiziksel `A1` koltuğu bağımsızdır; 1. etkinlikte satıldığında 2. etkinlikte `AVAILABLE` kalır ve ayrıca satılabilir | **PASS** |
| **T14** | `test_t14_order_ticket_code_collision_retries_and_unmasked_error` | Sipariş bilet üretiminde `ticket_code` çakışması (`23505` + `ix_tickets_ticket_code`) `SAVEPOINT` ile yeniden denenir; ilgisiz `IntegrityError` (`23502`) maskelenmeden dışarı aktarılır | **PASS** |
| **T23** | `test_t23_qr_decoded_independently_from_png_and_multi_ticket_pdf` | 3 koltuklu ve Türkçe karakterli sipariş için üretilen PNG ve PDF dosyasındaki QR görselleri bağımsız OpenCV (`cv2.QRCodeDetector`) + `pypdf` okuyucusuyla çözülür ve özgün `ticket_code` değerleriyle birebir eşleşir | **PASS** |
| **T24** | `test_t24_check_in_distinguishes_valid_used_fake_and_wrong_event` | Geçerli bilet (`ACCEPTED`, `VALID → USED`), kullanılmış bilet (`409 TICKET_ALREADY_USED` + ilk giriş zamanı), uydurma kod (`404 TICKET_NOT_FOUND`) ve yanlış etkinlik (`409 WRONG_EVENT`) doğru ayrılır | **PASS** |
| **T25** | `test_t25_concurrent_check_in_accepts_exactly_one` | İki bağımsız DB oturumu ve eşzamanlı bariyerle aynı QR koda yapılan iki check-in isteğinden `SELECT ... FOR UPDATE` sayesinde yalnızca 1 tanesi `ACCEPTED`, diğeri `409 TICKET_ALREADY_USED` alır; DB'de tek `CheckIn` kaydı oluşur | **PASS** |
| **T27** | `test_t27_email_delivery_failure_retries_without_breaking_sale_or_duplicating_tickets` | SMTP hatası siparişi ve biletleri bozmaz; 3 deneme (`10s`, `30s` backoff -> `FAILED`) doğru işler; 60 sn içinde tekrar istek `429 RATE_LIMITED` döner; sonraki başarılı gönderimde PDF ekiyle `SENT` olur ve bilet çoğalmaz | **PASS** |
