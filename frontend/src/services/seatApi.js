import { API_BASE_URL } from "../config";
import { request } from "./http";

const sessionBody = (sessionId) => JSON.stringify({ session_id: sessionId });

export function getSeats() {
  return request(`${API_BASE_URL}/seats/`);
}

export function lockSeat(seatId, sessionId) {
  return request(`${API_BASE_URL}/seats/${seatId}/lock`, {
    method: "POST",
    body: sessionBody(sessionId),
  });
}

export function releaseSeat(seatId, sessionId) {
  return request(`${API_BASE_URL}/seats/${seatId}/lock`, {
    method: "DELETE",
    body: sessionBody(sessionId),
  });
}

export function purchaseSeat(seatId, sessionId) {
  return request(`${API_BASE_URL}/seats/${seatId}/purchase`, {
    method: "POST",
    body: sessionBody(sessionId),
  });
}
