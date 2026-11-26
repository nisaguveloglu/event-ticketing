# Event Ticketing ve Koltuk Seçimi — Birinci Aşama (S1) ER Diyagramı

Aşağıdaki Mermaid ER diyagramı projenin Birinci Aşama (S1) veri modelini, fiziksel koltuk (`SEATS`) ile etkinlik bazlı doluluk (`EVENT_SEATS`) ayrımını, süreli rezervasyon (`RESERVATIONS`), sipariş (`ORDERS`), bilet (`TICKETS`), tek kullanımlık QR giriş (`CHECK_INS`), e-posta teslim kuyruğu (`EMAIL_DELIVERIES`) ve tekrar istek korumasını (`IDEMPOTENCY_RECORDS`) göstermektedir.

```mermaid
erDiagram
    HALLS ||--o{ SEAT_SEGMENTS : divides
    HALLS ||--o{ SEATS : contains
    SEAT_SEGMENTS ||--o{ SEATS : groups
    HALLS ||--o{ EVENTS : hosts
    EVENTS ||--o{ TICKET_CATEGORIES : defines
    EVENTS ||--o{ EVENT_SEATS : tracks
    SEATS ||--o{ EVENT_SEATS : mapped_to
    TICKET_CATEGORIES ||--o{ EVENT_SEATS : prices
    GUEST_SESSIONS ||--o{ RESERVATIONS : holds
    EVENTS ||--o{ RESERVATIONS : reserves_for
    RESERVATIONS ||--o{ RESERVATION_ITEMS : includes
    EVENT_SEATS ||--o{ RESERVATION_ITEMS : reserved_in
    RESERVATIONS |o--o{ EVENT_SEATS : current_lock
    GUEST_SESSIONS ||--o{ ORDERS : places
    RESERVATIONS ||--|| ORDERS : fulfilled_by
    ORDERS ||--|{ TICKETS : issues
    EVENTS ||--o{ TICKETS : for_event
    SEATS ||--o{ TICKETS : for_seat
    TICKETS ||--o| CHECK_INS : checked_in_by
    ORDERS ||--o{ EMAIL_DELIVERIES : delivers
    ORDERS ||--o{ IDEMPOTENCY_RECORDS : deduplicates

    HALLS {
        int id PK
        varchar name "NOT NULL"
        int stage_x "NOT NULL"
        int stage_y "NOT NULL"
    }

    SEAT_SEGMENTS {
        int id PK
        int hall_id FK "NOT NULL -> halls.id"
        varchar row_label "NOT NULL"
        boolean orphan_exempt "NOT NULL"
    }

    SEATS {
        int id PK
        int hall_id FK "NOT NULL -> halls.id"
        varchar row_label "NOT NULL"
        int number "NOT NULL"
        int row_order "NOT NULL"
        int segment_id FK "NOT NULL -> seat_segments.id"
        int x "NOT NULL"
        int y "NOT NULL"
        boolean is_accessible "NOT NULL"
    }

    EVENTS {
        int id PK
        int hall_id FK "NOT NULL -> halls.id"
        varchar name "NOT NULL"
        timestamptz starts_at "NOT NULL"
        boolean sales_open "NOT NULL"
        int version "NOT NULL"
    }

    TICKET_CATEGORIES {
        int id PK
        int event_id FK "NOT NULL -> events.id"
        varchar name "NOT NULL"
        int price_kurus "NOT NULL"
    }

    EVENT_SEATS {
        int id PK
        int event_id FK "NOT NULL, UQ(event_id, seat_id)"
        int seat_id FK "NOT NULL, UQ(event_id, seat_id)"
        int category_id FK "NOT NULL -> ticket_categories.id"
        int price_kurus "NOT NULL"
        seatstatus status "NOT NULL (AVAILABLE | LOCKED | SOLD)"
        int current_reservation_id FK "NULLABLE -> reservations.id"
    }

    GUEST_SESSIONS {
        int id PK
        varchar token_hash "UNIQUE, NOT NULL"
        timestamptz expires_at "NOT NULL"
    }

    RESERVATIONS {
        int id PK
        int event_id FK "NOT NULL -> events.id"
        int guest_session_id FK "NOT NULL -> guest_sessions.id"
        varchar status "NOT NULL (ACTIVE | PURCHASED | RELEASED | EXPIRED)"
        timestamptz created_at "NOT NULL"
        timestamptz expires_at "NOT NULL"
    }

    RESERVATION_ITEMS {
        int id PK
        int reservation_id FK "NOT NULL -> reservations.id"
        int event_seat_id FK "NOT NULL -> event_seats.id"
        int unit_price_kurus "NOT NULL"
    }

    ORDERS {
        int id PK
        int reservation_id FK "UNIQUE, NOT NULL -> reservations.id"
        int guest_session_id FK "NOT NULL -> guest_sessions.id"
        int total_price_kurus "NOT NULL"
        varchar currency "NOT NULL (TRY)"
        timestamptz created_at "NOT NULL"
    }

    TICKETS {
        int id PK
        int order_id FK "NOT NULL -> orders.id"
        int event_id FK "NOT NULL, UQ(event_id, seat_id)"
        int seat_id FK "NOT NULL, UQ(event_id, seat_id)"
        varchar ticket_code "UNIQUE INDEX (ix_tickets_ticket_code), NOT NULL"
        int unit_price_kurus "NOT NULL"
        varchar status "NOT NULL (VALID | USED)"
        timestamptz created_at "NOT NULL"
    }

    CHECK_INS {
        int id PK
        int ticket_id FK "UNIQUE, NOT NULL -> tickets.id"
        timestamptz checked_in_at "NOT NULL"
        varchar staff_label "NOT NULL"
    }

    EMAIL_DELIVERIES {
        int id PK
        int order_id FK "NOT NULL -> orders.id"
        varchar recipient "NOT NULL"
        varchar purpose "NOT NULL"
        varchar status "NOT NULL (PENDING | SENT | FAILED)"
        int attempts "NOT NULL"
        timestamptz next_attempt_at "NULLABLE"
        text last_error "NULLABLE"
        timestamptz sent_at "NULLABLE"
    }

    IDEMPOTENCY_RECORDS {
        int id PK
        varchar owner_key "NOT NULL, UQ(owner_key, key)"
        varchar key "NOT NULL, UQ(owner_key, key)"
        varchar request_hash "NOT NULL"
        int order_id FK "NOT NULL -> orders.id"
        timestamptz created_at "NOT NULL"
    }
```
