import { API_BASE_URL } from "../config";
import { request } from "./http";

export function getTicket(ticketCode) {
  return request(`${API_BASE_URL}/tickets/${encodeURIComponent(ticketCode)}`);
}

export function getTicketQrUrl(ticketCode) {
  return `${API_BASE_URL}/tickets/${encodeURIComponent(ticketCode)}/qr`;
}
