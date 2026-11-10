import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { connectSeatSocket } from "./seatSocket";

class FakeWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.listeners = new Map();
    FakeWebSocket.instances.push(this);
  }

  addEventListener(eventName, listener) {
    const listeners = this.listeners.get(eventName) || [];
    listeners.push(listener);
    this.listeners.set(eventName, listeners);
  }

  emit(eventName, event = {}) {
    this.listeners.get(eventName)?.forEach((listener) => listener(event));
  }

  close() {
    this.emit("close");
  }
}

describe("connectSeatSocket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("reports connection changes and forwards valid seat updates", () => {
    const onSeatUpdate = vi.fn();
    const onConnectionChange = vi.fn();
    const disconnect = connectSeatSocket({ onSeatUpdate, onConnectionChange });
    const socket = FakeWebSocket.instances[0];

    expect(onConnectionChange).toHaveBeenCalledWith("connecting");
    socket.emit("open");
    expect(onConnectionChange).toHaveBeenCalledWith("connected");

    socket.emit("message", {
      data: JSON.stringify({ seat_id: 5, status: "LOCKED" }),
    });
    expect(onSeatUpdate).toHaveBeenCalledWith({ seat_id: 5, status: "LOCKED" });

    socket.emit("message", { data: "not-json" });
    socket.emit("message", {
      data: JSON.stringify({ seat_id: "5", status: "LOCKED" }),
    });
    expect(onSeatUpdate).toHaveBeenCalledTimes(1);

    disconnect();
  });

  it("reconnects after an unexpected close and stops after cleanup", () => {
    const onConnectionChange = vi.fn();
    const disconnect = connectSeatSocket({ onConnectionChange });
    const firstSocket = FakeWebSocket.instances[0];

    firstSocket.emit("close");
    expect(onConnectionChange).toHaveBeenLastCalledWith("disconnected");

    vi.advanceTimersByTime(2000);
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(onConnectionChange).toHaveBeenLastCalledWith("connecting");

    disconnect();
    vi.advanceTimersByTime(2000);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });
});
