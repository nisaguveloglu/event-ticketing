# Event Ticketing ve Koltuk Seçimi — ER Diyagramı

Aşağıdaki Mermaid ER diyagramı projenin tek salon ve tek etkinlik prototipindeki beş ana tabloyu (`halls`, `seats`, `seat_locks`, `events`, `tickets`), birincil/yabancı anahtarları ve tekillik kısıtlarını/indekslerini göstermektedir.

```mermaid
erDiagram
    HALLS ||--o{ SEATS : contains
    HALLS ||--o{ EVENTS : hosts
    SEATS ||--o| SEAT_LOCKS : locked_by
    EVENTS ||--o{ TICKETS : issues
    SEATS ||--o{ TICKETS : sold_as

    HALLS {
        int id PK
        varchar name "NOT NULL"
    }

    SEATS {
        int id PK
        int hall_id FK "NOT NULL -> halls.id"
        varchar row "NOT NULL"
        int number "NOT NULL"
        seatstatus status "NOT NULL (ORM default: AVAILABLE)"
    }

    SEAT_LOCKS {
        int id PK
        int seat_id FK "UNIQUE, NOT NULL -> seats.id"
        varchar session_id "NOT NULL"
        timestamp created_at "NOT NULL"
    }

    EVENTS {
        int id PK
        int hall_id FK "NOT NULL -> halls.id"
        varchar name "NOT NULL"
        timestamptz starts_at "NOT NULL (roadmap: date)"
    }

    TICKETS {
        int id PK
        varchar ticket_code "UNIQUE INDEX (ix_tickets_ticket_code), NOT NULL"
        int event_id FK "NOT NULL -> events.id, UQ(event_id, seat_id)"
        int seat_id FK "NOT NULL -> seats.id, UQ(event_id, seat_id)"
        varchar session_id "NOT NULL"
        timestamptz created_at "NOT NULL, DEFAULT now()"
    }
```

## Kısıt, İndeks ve Varsayılan Değer Özeti

| Tablo | Kısıt / İndeks Adı | Kapsam | Açıklama |
|---|---|---|---|
| `halls` | `halls_pkey` (PK), `ix_halls_id` | `id` | Salon birincil anahtarı |
| `seats` | `seats_pkey` (PK), `seats_hall_id_fkey` (FK) | `id`, `hall_id -> halls(id)` | `status` sütunu veritabanında `NOT NULL` olup varsayılan değer (`SeatStatus.AVAILABLE`) SQLAlchemy ORM katmanında atanır |
| `seat_locks` | `seat_locks_seat_id_key` (UNIQUE) | `seat_id` | Aynı koltuk için aynı anda yalnızca tek aktif kilit bulunması |
| `events` | `events_pkey` (PK), `events_hall_id_fkey` (FK) | `id`, `hall_id -> halls(id)` | Etkinliğin düzenlendiği salon ve saat dilimi duyarlı başlangıç zamanı (`starts_at`) |
| `tickets` | `ix_tickets_ticket_code` (UNIQUE INDEX) | `ticket_code` | Hem ORM (`unique=True, index=True`) hem SQL şema dosyalarında tek ve tekrarsız unique index olarak tanımlanmıştır |
| `tickets` | `uq_tickets_event_seat` (UNIQUE CONSTRAINT) | `(event_id, seat_id)` | Aynı etkinlik ve aynı koltuk için birden fazla bilet kesilmesini veritabanı seviyesinde kesin olarak engeller |
