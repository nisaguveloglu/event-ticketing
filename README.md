# Main Project Structure

Projenin genel dizin yapısı aşağıdaki şekilde tutulmalıdır:

```text
event-ticketing/
│
├── frontend/
│
├── backend/
│
├── database/
│
├── docs/
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

Her ekip üyesi kendi alanında çalışırken bu ana yapıyı bozmamalıdır.

Yeni ana klasörler eklenmeden önce ekip içinde konuşulmalıdır.

---

# Frontend Structure

Frontend tarafı Ahmet tarafından geliştirilecektir.

Önerilen yapı:

```text
frontend/
│
├── src/
│   │
│   ├── components/
│   │   ├── Seat/
│   │   ├── SeatMap/
│   │   └── Ticket/
│   │
│   ├── pages/
│   │   ├── EventPage/
│   │   └── TicketPage/
│   │
│   ├── services/
│   │   ├── seatApi.js
│   │   └── ticketApi.js
│   │
│   ├── websocket/
│   │   └── seatSocket.js
│   │
│   ├── utils/
│   │
│   └── App.*
│
├── public/
│
└── package.json
```

Frontend tarafında mümkün olduğunca şu sorumluluk ayrımı korunmalıdır:

```text
components/
→ tekrar kullanılabilir UI parçaları

pages/
→ sayfa seviyesindeki yapılar

services/
→ backend REST API çağrıları

websocket/
→ WebSocket bağlantısı ve event handling

utils/
→ yardımcı fonksiyonlar
```

Önemli:

WebSocket kodu doğrudan SeatMap component içine gömülmemelidir.

Örneğin:

```text
frontend/src/websocket/seatSocket.js
```

gibi ayrı bir dosyada tutulmalıdır.

Aynı şekilde backend API çağrıları da component içinde doğrudan yazılmamalıdır.

Örneğin:

```text
frontend/src/services/seatApi.js
```

kullanılmalıdır.

---

# Backend Structure

Backend tarafı modüler FastAPI yapısı ile geliştirilmektedir.

Mevcut yapı:

```text
backend/
│
├── app/
│   │
│   ├── api/
│   │
│   │   └── seats.py
│   │
│   ├── core/
│   │   │   ├── config.py
│   │   │   └── database.py
│   │
│   ├── models/
│   │   │   ├── hall.py
│   │   │   ├── seat.py
│   │   │   └── seat_lock.py
│   │
│   ├── schemas/
│   │   │   ├── seat.py
│   │   │   └── seat_lock.py
│   │
│   ├── services/
│   │   │   └── seat_lock_service.py
│   │
│   ├── repositories/
│   │
│   ├── websocket/
│   │   │   └── manager.py
│   │
│   └── main.py
│
├── tests/
│
├── .env
└── venv/
```

Bu yapı korunmalıdır.

---

# Backend Folder Responsibilities

## app/api/

HTTP endpoint'leri burada bulunur.

Örnek:

```text
app/api/seats.py
```

Bu katmanın görevi:

```text
Request almak
↓
Service çağırmak
↓
Response döndürmek
```

Business logic mümkün olduğunca burada yazılmamalıdır.

Yanlış yaklaşım:

```text
API dosyasında:
- database query
- lock logic
- purchase logic
- WebSocket logic
- bütün kontroller
```

Doğru yaklaşım:

```text
API
↓
Service
↓
Database
```

---

## app/services/

Business logic burada bulunur.

Mevcut örnek:

```text
app/services/seat_lock_service.py
```

Şu anda burada:

```text
lock_seat()
release_seat()
purchase_seat()
```

işlemleri bulunmaktadır.

İleride örneğin:

```text
ticket_service.py
reservation_service.py
recommendation_service.py
```

gibi servisler eklenebilir.

---

## app/models/

SQLAlchemy database modelleri burada bulunur.

Mevcut modeller:

```text
hall.py
seat.py
seat_lock.py
```

Örneğin:

```text
Hall
Seat
SeatLock
```

Bu klasör yalnızca database modellerini temsil etmelidir.

---

## app/schemas/

FastAPI request ve response modelleri burada bulunur.

Pydantic kullanılmaktadır.

Mevcut örnekler:

```text
seat.py
seat_lock.py
```

Örneğin:

```text
SeatResponse
SeatLockRequest
```

Frontend'e dönen veya frontend'den gelen veri formatları burada tanımlanmalıdır.

---

## app/repositories/

Database erişimini ilerleyen aşamalarda service katmanından ayırmak için kullanılacaktır.

Örneğin:

```text
seat_repository.py
ticket_repository.py
```

İdeal akış:

```text
API
↓
Service
↓
Repository
↓
Database
```

Şu an bazı sorgular service içinde bulunmaktadır.

Proje büyüdükçe repository katmanına taşınabilir.

---

## app/websocket/

WebSocket connection management burada bulunur.

Mevcut dosya:

```text
manager.py
```

Görevi:

```text
WebSocket client bağlanması
WebSocket client çıkarılması
Connected client listesinin tutulması
Broadcast yapılması
```

WebSocket bağlantı yönetimi başka dosyalara dağıtılmamalıdır.

---

## app/core/

Backend genel yapılandırması burada bulunur.

Mevcut dosyalar:

```text
config.py
database.py
```

`config.py`

```text
environment configuration
```

`database.py`

```text
SQLAlchemy engine
SessionLocal
Base
get_db()
```

gibi ortak database altyapısını içerir.

---

## app/main.py

Uygulamanın başlangıç noktasıdır.

Burada yalnızca uygulamanın genel kurulumu tutulmalıdır.

Örneğin:

```text
FastAPI app creation
Router registration
WebSocket endpoint registration
Startup configuration
```

Business logic buraya eklenmemelidir.

Amaç:

```text
main.py küçük kalmalı
```

---

# Database Structure

Database tarafı ayrı bir klasör altında tutulmalıdır.

Önerilen yapı:

```text
database/
│
├── migrations/
│
├── seed/
│
├── schema/
│
└── diagrams/
```

---

## migrations/

Database değişiklikleri burada tutulmalıdır.

Örneğin:

```text
001_create_halls.sql
002_create_seats.sql
003_create_seat_locks.sql
004_create_tickets.sql
```

İleride Alembic gibi migration sistemi kullanılabilir.

---

## seed/

Test veya development için başlangıç verileri burada tutulmalıdır.

Örneğin:

```text
hall_seed.sql
seat_seed.sql
```

Örnek kullanım:

```text
Main Hall
A1
A2
A3
A4
B1
B2
B3
B4
```

---

## schema/

Database yapısını açıklayan dosyalar burada bulunabilir.

Örneğin:

```text
current_schema.sql
```

---

## diagrams/

ER diagram gibi database görselleri burada tutulabilir.

Örneğin:

```text
er-diagram.png
```

---

# Current Backend Data Model

Şu anda temel modeller şunlardır:

```text
Hall
Seat
SeatLock
```

İlişki:

```text
Hall
 │
 └── Seat
      │
      └── SeatLock
```

---

# Hall Model

Hall bir salonu temsil eder.

Alanlar:

```text
id
name
```

---

# Seat Model

Seat bir koltuğu temsil eder.

Alanlar:

```text
id
hall_id
row
number
status
```

Seat status:

```text
AVAILABLE
LOCKED
SOLD
```

---

# SeatLock Model

Bir koltuğun hangi session tarafından lock edildiğini tutar.

Alanlar:

```text
id
seat_id
session_id
created_at
```

`seat_id` unique tutulmaktadır.

Amaç:

```text
Aynı seat için aynı anda birden fazla lock kaydı oluşmasını engellemek.
```

---

# Current Backend Flow

Şu anda backend tarafında çalışan temel akış:

```text
Frontend
   ↓
REST API
   ↓
Backend
   ↓
Seat Service
   ↓
PostgreSQL
```

Seat lock sonrasında:

```text
Frontend
   ↓
POST /seats/{id}/lock
   ↓
Backend
   ↓
Seat = LOCKED
   ↓
Database Update
   ↓
WebSocket Broadcast
   ↓
Connected Clients
```

---

# Seat State Flow

Temel seat state geçişleri:

```text
AVAILABLE
    ↓
   LOCK
    ↓
 LOCKED
```

Kullanıcı seçimden vazgeçerse:

```text
LOCKED
    ↓
 RELEASE
    ↓
AVAILABLE
```

Satın alma tamamlanırsa:

```text
LOCKED
    ↓
 PURCHASE
    ↓
  SOLD
```

---

# Existing Backend Endpoints

## Get Seats

```text
GET /seats/
```

Frontend seat map'i oluştururken bu endpoint kullanılabilir.

Response örneği:

```json
[
  {
    "id": 1,
    "hall_id": 1,
    "row": "A",
    "number": 1,
    "status": "AVAILABLE"
  }
]
```

---

## Lock Seat

```text
POST /seats/{seat_id}/lock
```

Request:

```json
{
  "session_id": "user-a"
}
```

Başarılı durumda:

```text
Seat → LOCKED
```

---

## Release Seat

```text
DELETE /seats/{seat_id}/lock
```

Request:

```json
{
  "session_id": "user-a"
}
```

Başarılı durumda:

```text
Seat → AVAILABLE
```

---

## Purchase Seat

```text
POST /seats/{seat_id}/purchase
```

Request:

```json
{
  "session_id": "user-a"
}
```

Başarılı durumda:

```text
Seat → SOLD
```

Şu anda gerçek ödeme yapılmamaktadır.

Purchase yalnızca backend akışını simüle etmektedir.

---

# WebSocket Contract

Frontend ile backend arasındaki WebSocket endpoint:

```text
ws://127.0.0.1:8000/ws/seats
```

Backend seat durumu değiştiğinde aşağıdaki formatta mesaj gönderir.

Lock:

```json
{
  "seat_id": 5,
  "status": "LOCKED"
}
```

Release:

```json
{
  "seat_id": 5,
  "status": "AVAILABLE"
}
```

Purchase:

```json
{
  "seat_id": 5,
  "status": "SOLD"
}
```

Frontend WebSocket client bu formatı değiştirmeden kullanmalıdır.

Bu format frontend-backend entegrasyonu için ortak contract olarak kabul edilmelidir.

---

# Frontend Integration Rule

Frontend tarafında seat state mümkün olduğunca backend'den gelen status ile aynı isimleri kullanmalıdır.

Kullanılacak değerler:

```text
AVAILABLE
LOCKED
SOLD
```

Örneğin frontend tarafında:

```javascript
if (seat.status === "AVAILABLE") {
    ...
}

if (seat.status === "LOCKED") {
    ...
}

if (seat.status === "SOLD") {
    ...
}
```

Backend değerlerini frontend tarafında farklı isimlere çevirmemek entegrasyonu kolaylaştıracaktır.

---

# Database Integration Rule

Database model isimleri ve temel ilişkiler değiştirilmeden önce ekip ile konuşulmalıdır.

Özellikle şu alanlar ortak contract olarak kullanılmaktadır:

```text
hall.id
seat.id
seat.hall_id
seat.row
seat.number
seat.status
seat_lock.seat_id
seat_lock.session_id
```

Murat ticket sistemi geliştirirken mümkün olduğunca mevcut modeller üzerinden ilişki kurmalıdır.

Örneğin ileride:

```text
Ticket
 │
 ├── seat_id
 └── event_id
```

şeklinde ilerlenebilir.

---

# Recommended Future Project Structure

Proje ilerlediğinde genel yapı şu şekilde genişletilebilir:

```text
event-ticketing/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── websocket/
│   │   └── utils/
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── websocket/
│   │   └── main.py
│   └── tests/
│
├── database/
│   ├── migrations/
│   ├── seed/
│   ├── schema/
│   └── diagrams/
│
├── docs/
│   ├── architecture/
│   ├── diagrams/
│   └── report/
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

# Development Rules

Projenin yönetilebilir kalması için aşağıdaki kurallar uygulanmalıdır.

## 1. Her şeyi tek dosyada yazmayın

Yanlış:

```text
main.py
 ├── database
 ├── seat logic
 ├── websocket
 ├── ticket
 ├── QR
 └── API
```

Doğru:

```text
api/
services/
models/
schemas/
repositories/
websocket/
```

---

## 2. Her sorumluluk kendi klasöründe tutulmalı

Frontend API çağrıları:

```text
frontend/src/services/
```

Frontend WebSocket:

```text
frontend/src/websocket/
```

Backend API:

```text
backend/app/api/
```

Backend business logic:

```text
backend/app/services/
```

Database modelleri:

```text
backend/app/models/
```

---

## 3. Ortak veri isimlerini değiştirmeyin

Örneğin:

```text
seat_id
session_id
status
hall_id
```

gibi isimler frontend, backend ve database arasında mümkün olduğunca aynı tutulmalıdır.

---

## 4. Yeni özellikler ayrı dosyalarda geliştirilmelidir

Örneğin QR geldiğinde:

```text
backend/app/services/ticket_service.py
backend/app/services/qr_service.py
backend/app/models/ticket.py
backend/app/schemas/ticket.py
```

gibi ayrılmalıdır.

---

## 5. Main branch doğrudan geliştirme için kullanılmamalıdır

Her kişi kendi feature branch üzerinde çalışmalıdır.

Örnek:

```text
feature/frontend
feature/backend
feature/database
```

Tamamlanan çalışmalar Pull Request ile birleştirilmelidir.

---

# Current Completed Backend Work

Şu ana kadar tamamlanan backend altyapısı:

```text
✓ FastAPI project structure
✓ PostgreSQL connection
✓ SQLAlchemy setup
✓ Hall model
✓ Seat model
✓ SeatLock model
✓ Seat status enum
✓ GET /seats
✓ Basic seat lock
✓ Lock ownership with session_id
✓ Lock release
✓ Purchase simulation
✓ SOLD protection
✓ Basic WebSocket manager
✓ WebSocket connection
✓ LOCKED broadcast
✓ AVAILABLE broadcast
✓ SOLD broadcast
```

---

# Important Integration Point

Frontend, backend ve database birbirinden bağımsız projeler gibi geliştirilmemelidir.

Ortak akış:

```text
Frontend
   ↓
REST / WebSocket
   ↓
Backend
   ↓
Service Layer
   ↓
Database
```

Her ekip üyesi kendi geliştirmesini bu yapıya uyumlu yapmalıdır.

Amaç:

```text
Frontend'in backend kodunu bilmesine gerek olmaması

Backend'in frontend implementasyonunu bilmesine gerek olmaması

Database tarafının API detaylarını bilmesine gerek olmaması
```

Taraflar yalnızca ortak API ve data contract üzerinden haberleşmelidir.

---

# Summary

Takımın kullanacağı temel mimari:

```text
Frontend
├── components
├── pages
├── services
└── websocket

Backend
├── api
├── services
├── repositories
├── models
├── schemas
├── websocket
└── core

Database
├── migrations
├── seed
├── schema
└── diagrams

Docs
├── architecture
├── diagrams
└── report
```

Bu yapı proje boyunca mümkün olduğunca korunmalıdır.
