import { WS_URL } from "../config";

export function connectSeatSocket({ onSeatUpdate, onConnectionChange }) {
  let socket;
  let reconnectTimer;
  let closedByClient = false;

  const connect = () => {
    onConnectionChange?.("connecting");
    socket = new WebSocket(WS_URL);

    socket.addEventListener("open", () => onConnectionChange?.("connected"));
    socket.addEventListener("message", (event) => {
      try {
        const update = JSON.parse(event.data);
        if (Number.isInteger(update.seat_id) && update.status) {
          onSeatUpdate(update);
        }
      } catch {
        // Ignore malformed messages without interrupting future updates.
      }
    });
    socket.addEventListener("close", () => {
      onConnectionChange?.("disconnected");
      if (!closedByClient) reconnectTimer = window.setTimeout(connect, 2000);
    });
    socket.addEventListener("error", () => socket.close());
  };

  connect();

  return () => {
    closedByClient = true;
    window.clearTimeout(reconnectTimer);
    socket?.close();
  };
}
