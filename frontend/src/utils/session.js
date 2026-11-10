const SESSION_KEY = "event-ticketing-session-id";

export function getSessionId() {
  const existingSessionId = window.sessionStorage.getItem(SESSION_KEY);
  if (existingSessionId) return existingSessionId;

  const sessionId = `web-${crypto.randomUUID()}`;
  window.sessionStorage.setItem(SESSION_KEY, sessionId);
  return sessionId;
}
