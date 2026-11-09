# Backend Kurulum, Çalıştırma ve Test Rehberi (PowerShell)

Aşağıdaki tüm komut blokları proje kök dizini (`event-ticketing`) başlangıç dizini alınarak taşınabilir biçimde yazılmıştır.

## 1. Ön Koşullar

- Docker Desktop çalışır durumda olmalıdır (`Engine running`).
- Python 3.13 kurulu olmalıdır.

## 2. PostgreSQL Servisini Başlatma

**Başlangıç dizini:** Proje kök dizini (`event-ticketing`)

```powershell
docker compose up -d postgres
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL container baslatilamadi (exit code: $LASTEXITCODE)." }
```

> **Önemli:** Mevcut verileri ve Docker volume'ünü korumak için `docker compose down -v` komutunu **kullanmayın**.

## 3. Sanal Ortam ve Bağımlılıkların Kurulumu

**Başlangıç dizini:** Proje kök dizini (`event-ticketing`) — komut bloğu `backend` dizinine geçip tamamlandığında tekrar proje kök dizinine döner:

```powershell
Push-Location .\backend
try {
    if (-not (Test-Path .\venv)) {
        py -3.13 -m venv venv
        if ($LASTEXITCODE -ne 0) { throw "Sanal ortam olusturulamadi." }
    }
    .\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "Bagimlilik kurulumu basarisiz oldu." }
} finally {
    Pop-Location
}
```

## 4. Ortam Değişkenleri (`backend/.env`)

`app/core/config.py` içindeki `Settings` sınıfı çalışma dizinindeki `.env` dosyasından yalnızca `DATABASE_URL` alanını okur. `backend/.env` dosyası mevcut değilse `backend/.env.example` şablonunu kopyalayarak oluşturun (mevcut `backend/.env` dosyanız varsa üzerine yazmayın):

**Başlangıç dizini:** Proje kök dizini (`event-ticketing`) — komut bloğu `backend` dizinine geçip tamamlandığında tekrar proje kök dizinine döner:

```powershell
Push-Location .\backend
try {
    if (-not (Test-Path .\.env)) {
        Copy-Item .\.env.example .\.env
    }
} finally {
    Pop-Location
}
```

## 5. Backend Sunucusunu Başlatma

`.env` dosyasının doğru okunması için `uvicorn` süreci `backend` dizini içinden çalışmalıdır. Aşağıdaki komut bloğu proje kök dizininden başlayıp `backend` dizinine geçer ve sunucuyu başlatır:

**Başlangıç dizini:** Proje kök dizini (`event-ticketing`)

```powershell
cd .\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

> **Terminal Notu:** `uvicorn` çalıştığı sürece bu PowerShell terminali sunucu tarafından meşgul tutulur (ve çalışma dizini `backend` olarak kalır). Sunucuyu kapatmadan **Bölüm 6 (Seed)** ve **Bölüm 7 (Test)** adımlarını uygulamak için proje kök dizininde (`event-ticketing`) **yeni/ayrı bir PowerShell terminali** açın.

Sunucu başladığında `Base.metadata.create_all(bind=engine)` eksik tabloları (`halls`, `seats`, `seat_locks`, `events`, `tickets`) mevcut verileri silmeden oluşturur.

> **Şema Notu:** Gerek `Base.metadata.create_all` gerekse `database/` altındaki `CREATE TABLE IF NOT EXISTS` ifadeleri yalnızca henüz mevcut olmayan tabloları/indeksleri oluşturur; daha önce farklı sütun, varsayılan değer veya kısıtlarla oluşturulmuş mevcut bir tablonun şemasını otomatik olarak değiştirmez (`ALTER TABLE` yapmaz).

Swagger UI adresi:
- `http://127.0.0.1:8001/docs`

## 6. İdempotent Seed Dosyasını Çalıştırma

**Başlangıç dizini:** Proje kök dizininde (`event-ticketing`) açılan **ayrı bir PowerShell terminali** (`uvicorn` çalışan terminal meşgul olduğu için):

Mevcut salonu, koltukları (ID ve durumlarıyla), kilitleri ve biletleri koruyarak prototipin tek demo etkinliğini (`Opening Night Concert`) eklemek için:

```powershell
Get-Content .\database\seed\001_main_hall_event_seed.sql -Raw | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d cinema
if ($LASTEXITCODE -ne 0) { throw "Seed calistirma islemi basarisiz oldu (exit code: $LASTEXITCODE)." }
```

Bu betik:
- Hiç salon yoksa `Main Hall` salonunu, `A1`–`A6` koltuklarını ve `Opening Night Concert` etkinliğini oluşturur.
- Tek uygun `Main Hall` salonu varsa mevcut koltukların ID, durum (`AVAILABLE`/`LOCKED`/`SOLD`), kilit ve biletlerini değiştirmeden eksik koltuk/etkinliği tamamlar; tekrar çalıştırıldığında kopya kayıt üretmez.
- Birden fazla salon/etkinlik veya prototiple uyumsuz mevcut bir salon/etkinlik durumu varsa transaction içinde açık hata (`RAISE EXCEPTION`) vererek hiçbir değişiklik yapmadan durur.

## 7. İzole Test Veritabanında (`cinema_test`) Testleri Çalıştırma

Testler demo veritabanına (`cinema`) dokunmaz; ayrı `cinema_test` veritabanını kullanır. `TEST_DATABASE_URL` değeri `.env` dosyasına yazılmaz, PowerShell ortam değişkeni olarak verilir. `uvicorn` çalışıyorsa aşağıdaki adımları proje kök dizininde (`event-ticketing`) açılan **ayrı bir PowerShell terminalinden** yürütün.

**Adım 7.1 — `cinema_test` veritabanını kontrol etme ve yoksa oluşturma**
**Başlangıç dizini:** Proje kök dizini (`event-ticketing`)

```powershell
$dbCheck = docker compose exec -T postgres psql -U postgres -Atc "SELECT 1 FROM pg_database WHERE datname = 'cinema_test'"
if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL baglanti veya sorgu hatasi (exit code: $LASTEXITCODE)."
}

$dbExists = ($dbCheck -split "`r?`n" | ForEach-Object { $_.Trim() }) -contains "1"
if (-not $dbExists) {
    docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -c "CREATE DATABASE cinema_test;"
    if ($LASTEXITCODE -ne 0) {
        throw "cinema_test veritabani olusturulamadi (exit code: $LASTEXITCODE)."
    }
}
```

**Adım 7.2 — Pytest çalıştırma**
**Başlangıç dizini:** Proje kök dizini (`event-ticketing`) — komut bloğu `backend` dizinine geçip testleri çalıştırdıktan sonra tekrar proje kök dizinine döner:

```powershell
Push-Location .\backend
try {
    $env:TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/cinema_test"
    .\venv\Scripts\python.exe -m pytest -v
    if ($LASTEXITCODE -ne 0) { throw "Test paketi basarisiz oldu (exit code: $LASTEXITCODE)." }
} finally {
    Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
    Pop-Location
}
```
