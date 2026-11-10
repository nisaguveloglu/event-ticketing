import { getTicketQrUrl } from "../../services/ticketApi";

export default function Ticket({ ticket, onClose }) {
  const eventDate = new Intl.DateTimeFormat("en", {
    dateStyle: "long",
    timeStyle: "short",
  }).format(new Date(ticket.event_starts_at));

  return (
    <section className="ticket" aria-labelledby="ticket-title">
      <div>
        <p className="eyebrow">Purchase complete</p>
        <h2 id="ticket-title">{ticket.event_name}</h2>
        <dl>
          <div><dt>Date</dt><dd>{eventDate}</dd></div>
          <div><dt>Hall</dt><dd>{ticket.hall_name}</dd></div>
          <div><dt>Seat</dt><dd>{ticket.seat_row}{ticket.seat_number}</dd></div>
          <div><dt>Ticket code</dt><dd>{ticket.ticket_code}</dd></div>
        </dl>
        <button className="button button--secondary" type="button" onClick={onClose}>
          Back to seat map
        </button>
      </div>
      <div className="ticket__qr">
        <img src={getTicketQrUrl(ticket.ticket_code)} alt={`QR code for ticket ${ticket.ticket_code}`} />
        <span>Present this code at the entrance</span>
      </div>
    </section>
  );
}
