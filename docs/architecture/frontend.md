# Frontend Architecture and Integration Guide

## Scope

The frontend implements the Member 1 responsibilities for the interim project: seat map rendering, seat selection, REST integration, live WebSocket updates, purchase confirmation, and ticket/QR presentation.

## Technology

- React for components and page state
- Vite for development and production builds
- Native `fetch` for REST requests
- Native `WebSocket` for live seat status updates
- Vitest and Testing Library for component tests

No global state library is required for the current single-page scope.

## Source Structure

```text
frontend/src/
├── components/
│   ├── Seat/
│   ├── SeatMap/
│   ├── StatusLegend/
│   └── Ticket/
├── pages/
│   └── EventPage/
├── services/
│   ├── http.js
│   ├── seatApi.js
│   └── ticketApi.js
├── websocket/
│   └── seatSocket.js
├── utils/
│   └── session.js
├── config.js
└── App.jsx
```

UI components do not contain backend URLs or raw request code. REST requests remain in `services/`, and WebSocket lifecycle management remains in `websocket/`.

## Seat State Rules

Backend states are preserved without renaming:

| Status | Meaning | Selectable |
| --- | --- | --- |
| `AVAILABLE` | Seat is free | Yes |
| `LOCKED` | Another session currently holds the seat | No |
| `SOLD` | Purchase is complete | No |
| `SELECTED` | Client-only display for the current session's locked seat | Yes, to release |

`SELECTED` is never sent to the backend. The frontend calculates it by comparing the seat ID with `selectedSeatId`.

## REST Contract

```text
GET    /seats/
POST   /seats/{seat_id}/lock
DELETE /seats/{seat_id}/lock
POST   /seats/{seat_id}/purchase
GET    /tickets/{ticket_code}
GET    /tickets/{ticket_code}/qr
```

Lock, release, and purchase requests use:

```json
{
  "session_id": "web-generated-session-id"
}
```

The browser session ID is created once per tab and stored in `sessionStorage`. Separate browser tabs therefore behave as separate users during concurrency demonstrations.

## WebSocket Contract

The client connects to `/ws/seats` and accepts messages in this format:

```json
{
  "seat_id": 5,
  "status": "LOCKED"
}
```

The same structure is used for `AVAILABLE` and `SOLD`. The UI updates without a page refresh. Malformed messages are ignored, and a closed connection retries after two seconds.

## Local Integration

The Vite development server listens on port `5173` and proxies REST and WebSocket traffic to the FastAPI backend on port `8001`. This matches `backend/README.md` and avoids a development-only CORS dependency.

```text
Browser → http://127.0.0.1:5173
             ├── /seats/*   → http://127.0.0.1:8001
             ├── /tickets/* → http://127.0.0.1:8001
             └── /ws/*      → ws://127.0.0.1:8001
```

If the backend runs on another address, copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL` and `VITE_WS_URL`.

## Team Integration Checklist

Before merging the frontend branch:

- Start PostgreSQL and apply the project seed.
- Start FastAPI on port `8001`.
- Confirm `GET /seats/` returns seeded seats.
- Start the frontend with `npm run dev`.
- Open two separate browser tabs.
- Select one seat in Browser A.
- Confirm Browser B receives `LOCKED` without refreshing.
- Release the seat in Browser A.
- Confirm Browser B receives `AVAILABLE`.
- Purchase a locked seat.
- Confirm both clients display `SOLD`.
- Confirm ticket details load using the returned `ticket_code`.
- Confirm the QR endpoint displays a PNG.
- Run `npm test` and `npm run build` before opening the pull request.

## Known Project Boundary

The frontend currently supports a single event and hall flow because the backend seat listing endpoint does not yet require an event or hall parameter. Event selection and authentication belong to future project scope unless the shared API contract changes.
