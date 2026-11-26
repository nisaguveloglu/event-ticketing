# Birinci Aşama (S1) Veri Sözlüğü, Yedekleme ve K0 Başlangıç Kaydı

## 1. K0 Başlangıç ve Veritabanı Yedekleme / Geri Yükleme

- **İncelenen Temel Sürüm (Baseline Commit):** `20a8cc8` (`main`)
- **İzole Test Veritabanı:** `event_ticketing_test` (`postgresql+psycopg2://postgres:postgres@localhost:5432/event_ticketing_test`)
- **Yedek Alma Komutu (Proje kök dizininde):**
  ```powershell
  docker compose exec -T postgres pg_dump -U postgres -d cinema --clean --if-exists > .\database\backup_pre_s1.sql
  ```
- **Geri Yükleme (Restore) Komutu:**
  ```powershell
  Get-Content .\database\backup_pre_s1.sql -Raw | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d cinema
  ```

---

## 2. S1 Tablo ve Alan Sözlüğü (M1)

### `halls` (`Hall`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Salon kimliği |
| `name` | `VARCHAR(100)` | `NOT NULL` | Salon adı (`Main Hall`, `Studio Hall`) |
| `stage_x` | `INTEGER` | `NOT NULL, DEFAULT 0` | Sahne merkez X koordinatı |
| `stage_y` | `INTEGER` | `NOT NULL, DEFAULT 0` | Sahne merkez Y koordinatı |

### `seat_segments` (`SeatSegment`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Segment kimliği |
| `hall_id` | `INTEGER` | `NOT NULL, FK -> halls.id` | Ait olduğu salon |
| `row_label` | `VARCHAR(10)` | `NOT NULL` | Sıra etiketi (`A`, `B`, `C`, `D`) |
| `orphan_exempt` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Tek boş koltuk kuralından muaf segment (erişilebilir `A1` segmenti için `TRUE`) |

### `seats` (`Seat`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Fiziksel koltuk kimliği (API `seat_ids` alanı bu kimliği kullanır) |
| `hall_id` | `INTEGER` | `NOT NULL, FK -> halls.id` | Ait olduğu salon |
| `row_label` | `VARCHAR(10)` | `NOT NULL` | Görünür sıra etiketi (`A`–`D`) |
| `number` | `INTEGER` | `NOT NULL` | Sıra içi koltuk numarası |
| `row_order` | `INTEGER` | `NOT NULL` | Sahneye göre sıra sırası (`1, 2, 3...`) |
| `segment_id` | `INTEGER` | `NOT NULL, FK -> seat_segments.id` | Koridorla ayrılmış segment kimliği |
| `x` | `INTEGER` | `NOT NULL` | Görsel X koordinatı |
| `y` | `INTEGER` | `NOT NULL` | Görsel Y koordinatı |
| `is_accessible` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Erişilebilir koltuk bayrağı (`A1` için `TRUE`) |
| `row` | `VARCHAR(10)` | `NOT NULL` | Geriye dönüş uyumu için korunan eski sıra alanı |
| `status` | `seatstatus` | `NOT NULL` | İkinci aşama kabulüne kadar geriye dönüş için korunan eski alan (uygulama doluluğu `event_seats.status` üzerinden okur) |

### `events` (`Event`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Etkinlik kimliği |
| `hall_id` | `INTEGER` | `NOT NULL, FK -> halls.id` | Düzenlendiği salon |
| `name` | `VARCHAR(200)` | `NOT NULL` | Etkinlik adı |
| `starts_at` | `TIMESTAMPTZ` | `NOT NULL` | Etkinlik başlangıç zamanı (UTC) |
| `sales_open` | `BOOLEAN` | `NOT NULL, DEFAULT TRUE` | Satışa açık durumu |
| `version` | `INTEGER` | `NOT NULL, DEFAULT 1` | Her durum değişiminde aynı transaction içinde artırılan etkinlik sürüm sayacı |

### `ticket_categories` (`TicketCategory`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Kategori kimliği |
| `event_id` | `INTEGER` | `NOT NULL, FK -> events.id` | Ait olduğu etkinlik |
| `name` | `VARCHAR(100)` | `NOT NULL` | Kategori adı (`Premium`, `Standard`) |
| `price_kurus` | `INTEGER` | `NOT NULL` | Kuruş cinsinden birim fiyat (`50000`, `30000`, `25000`) |

### `event_seats` (`EventSeat`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Etkinlik koltuk kaydı kimliği |
| `event_id` | `INTEGER` | `NOT NULL, FK -> events.id, UQ(event_id, seat_id)` | Etkinlik kimliği |
| `seat_id` | `INTEGER` | `NOT NULL, FK -> seats.id, UQ(event_id, seat_id)` | Fiziksel koltuk kimliği |
| `category_id` | `INTEGER` | `NOT NULL, FK -> ticket_categories.id` | Kategori kimliği |
| `price_kurus` | `INTEGER` | `NOT NULL` | Etkinlik koltuğunun kuruş cinsinden satış bedeli |
| `status` | `seatstatus` | `NOT NULL` | `AVAILABLE`, `LOCKED`, `SOLD` |
| `current_reservation_id` | `INTEGER` | `NULLABLE, FK -> reservations.id` | Aktif rezervasyon bağı |

### `guest_sessions` (`GuestSession`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Misafir oturum kimliği |
| `token_hash` | `VARCHAR(64)` | `NOT NULL, UNIQUE` | 32 byte rastgele oturum tokeninin SHA-256 özeti |
| `expires_at` | `TIMESTAMPTZ` | `NOT NULL` | Oturum son kullanma zamanı (UTC) |

### `reservations` (`Reservation`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Rezervasyon kimliği |
| `event_id` | `INTEGER` | `NOT NULL, FK -> events.id` | Etkinlik kimliği |
| `guest_session_id` | `INTEGER` | `NOT NULL, FK -> guest_sessions.id` | Sahip misafir oturumu (partial unique index: `WHERE status = 'ACTIVE'`) |
| `status` | `VARCHAR(20)` | `NOT NULL` | `ACTIVE`, `PURCHASED`, `RELEASED`, `EXPIRED` |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | Oluşturulma zamanı (UTC) |
| `expires_at` | `TIMESTAMPTZ` | `NOT NULL` | Bitiş zamanı (`created_at + 300s`, güncellemede uzamaz) |

### `reservation_items` (`ReservationItem`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Rezervasyon kalemi kimliği |
| `reservation_id` | `INTEGER` | `NOT NULL, FK -> reservations.id` | Bağlı rezervasyon |
| `event_seat_id` | `INTEGER` | `NOT NULL, FK -> event_seats.id, UQ(reservation_id, event_seat_id)` | Seçilen etkinlik koltuğu |
| `unit_price_kurus` | `INTEGER` | `NOT NULL` | Rezervasyon anındaki anlık birim fiyat (kuruş) |

### `orders` (`Order`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Sipariş kimliği |
| `reservation_id` | `INTEGER` | `NOT NULL, UNIQUE, FK -> reservations.id` | Satın alınan rezervasyon |
| `guest_session_id` | `INTEGER` | `NOT NULL, FK -> guest_sessions.id` | Sipariş sahibi misafir oturumu |
| `total_price_kurus` | `INTEGER` | `NOT NULL` | Toplam sipariş tutarı (kuruş) |
| `currency` | `VARCHAR(10)` | `NOT NULL, DEFAULT 'TRY'` | Para birimi (`TRY`) |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | Sipariş zamanı (UTC) |

### `tickets` (`Ticket`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Bilet kimliği |
| `order_id` | `INTEGER` | `NOT NULL, FK -> orders.id` | Bağlı sipariş |
| `event_id` | `INTEGER` | `NOT NULL, FK -> events.id, UQ(event_id, seat_id)` | Etkinlik kimliği |
| `seat_id` | `INTEGER` | `NOT NULL, FK -> seats.id, UQ(event_id, seat_id)` | Fiziksel koltuk kimliği |
| `ticket_code` | `VARCHAR(64)` | `NOT NULL, UNIQUE INDEX (ix_tickets_ticket_code)` | Opak ve tahmin edilemeyen bilet kodu |
| `unit_price_kurus` | `INTEGER` | `NOT NULL` | Satın alma anındaki birim bilet fiyatı (kuruş) |
| `status` | `VARCHAR(20)` | `NOT NULL, DEFAULT 'VALID'` | `VALID` veya `USED` |
| `session_id` | `VARCHAR(100)` | `NOT NULL` | Geriye dönüş uyumu için korunan alan |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | Oluşturulma zamanı (UTC) |

### `check_ins` (`CheckIn`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Giriş kontrol kaydı kimliği |
| `ticket_id` | `INTEGER` | `NOT NULL, UNIQUE, FK -> tickets.id` | Doğrulanan bilet (`UNIQUE` ile tek kullanımlık garanti) |
| `checked_in_at` | `TIMESTAMPTZ` | `NOT NULL` | Sunucu kabul zamanı (UTC) |
| `staff_label` | `VARCHAR(100)` | `NOT NULL` | Görevli etiketi |

### `email_deliveries` (`EmailDelivery`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Teslim işi kimliği |
| `order_id` | `INTEGER` | `NOT NULL, FK -> orders.id` | İlgili sipariş |
| `recipient` | `VARCHAR(255)` | `NOT NULL` | Alıcı e-posta adresi |
| `purpose` | `VARCHAR(50)` | `NOT NULL, DEFAULT 'ORDER_TICKETS'` | Teslim amacı |
| `status` | `VARCHAR(20)` | `NOT NULL` | `PENDING`, `SENT`, `FAILED` |
| `attempts` | `INTEGER` | `NOT NULL, DEFAULT 0` | Deneme sayısı (en fazla 3) |
| `next_attempt_at` | `TIMESTAMPTZ` | `NULLABLE` | Sonraki deneme zamanı |
| `last_error` | `TEXT` | `NULLABLE` | Son hata açıklaması |
| `sent_at` | `TIMESTAMPTZ` | `NULLABLE` | Başarılı gönderim zamanı |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | İş oluşturulma zamanı |

### `idempotency_records` (`IdempotencyRecord`)
| Alan | Tür | Kısıtlar | Açıklama |
|---|---|---|---|
| `id` | `INTEGER` | `PK` | Tekrar istek kaydı kimliği |
| `owner_key` | `VARCHAR(100)` | `NOT NULL, UQ(owner_key, key)` | Sahip anahtarı (`g:<GuestSession.id>`) |
| `key` | `VARCHAR(100)` | `NOT NULL, UQ(owner_key, key)` | `Idempotency-Key` başlık değeri |
| `request_hash` | `VARCHAR(64)` | `NOT NULL` | İstek gövdesi SHA-256 özeti |
| `order_id` | `INTEGER` | `NOT NULL, FK -> orders.id` | Oluşturulan sipariş |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | Kayıt zamanı (24 saat korunur) |
