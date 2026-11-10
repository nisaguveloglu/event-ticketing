const trimTrailingSlash = (value) => value.replace(/\/$/, "");

export const API_BASE_URL = trimTrailingSlash(import.meta.env.VITE_API_BASE_URL || "");

const browserWebSocketUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/seats`;

export const WS_URL = import.meta.env.VITE_WS_URL || browserWebSocketUrl;
