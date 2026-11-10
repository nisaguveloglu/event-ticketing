# Event Ticketing Frontend

React and Vite client for the seat selection, live seat synchronization, purchase, ticket, and QR flow.

## Local setup

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

The Vite development server proxies `/seats`, `/tickets`, and `/ws` to `http://127.0.0.1:8001`, matching the backend run guide. This allows local development without a CORS change. Set `VITE_BACKEND_PROXY_TARGET` in `.env.local` when the backend uses another origin or port.

## Commands

```bash
npm run dev
npm test
npm run build
```

## Source responsibilities

- `components/`: reusable UI elements
- `pages/`: page-level state and workflows
- `services/`: REST API requests
- `websocket/`: live seat status connection
- `utils/`: browser session helpers

## Integration contract

The frontend preserves backend seat statuses: `AVAILABLE`, `LOCKED`, and `SOLD`. `SELECTED` is a client-only display status for the seat locked by the current browser session.

In production, serve the frontend and API behind the same origin or allow the frontend origin through FastAPI CORS middleware.
