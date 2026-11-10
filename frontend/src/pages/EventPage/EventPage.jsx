import { useEffect, useMemo, useRef, useState } from "react";
import SeatMap from "../../components/SeatMap/SeatMap";
import StatusLegend from "../../components/StatusLegend/StatusLegend";
import Ticket from "../../components/Ticket/Ticket";
import { getSeats, lockSeat, purchaseSeat, releaseSeat } from "../../services/seatApi";
import { getTicket } from "../../services/ticketApi";
import { getSessionId } from "../../utils/session";
import { connectSeatSocket } from "../../websocket/seatSocket";

export default function EventPage() {
  const sessionId = useRef(getSessionId());
  const [seats, setSeats] = useState([]);
  const [selectedSeatId, setSelectedSeatId] = useState(null);
  const [busySeatId, setBusySeatId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState("connecting");
  const [ticket, setTicket] = useState(null);

  const selectedSeat = useMemo(
    () => seats.find((seat) => seat.id === selectedSeatId),
    [seats, selectedSeatId],
  );

  useEffect(() => {
    getSeats()
      .then(setSeats)
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));

    return connectSeatSocket({
      onConnectionChange: setConnection,
      onSeatUpdate: ({ seat_id: seatId, status }) => {
        setSeats((currentSeats) =>
          currentSeats.map((seat) => seat.id === seatId ? { ...seat, status } : seat),
        );
        setSelectedSeatId((currentSeatId) =>
          currentSeatId === seatId && status !== "LOCKED" ? null : currentSeatId,
        );
      },
    });
  }, []);

  const handleSeatSelection = async (seat) => {
    setError("");
    setBusySeatId(seat.id);

    try {
      if (selectedSeatId === seat.id) {
        await releaseSeat(seat.id, sessionId.current);
        setSelectedSeatId(null);
        return;
      }

      if (selectedSeatId) {
        await releaseSeat(selectedSeatId, sessionId.current);
        setSelectedSeatId(null);
      }

      await lockSeat(seat.id, sessionId.current);
      setSelectedSeatId(seat.id);
    } catch (requestError) {
      setError(requestError.message);
      const freshSeats = await getSeats().catch(() => null);
      if (freshSeats) setSeats(freshSeats);
    } finally {
      setBusySeatId(null);
    }
  };

  const handlePurchase = async () => {
    if (!selectedSeatId) return;
    setError("");
    setBusySeatId(selectedSeatId);

    try {
      const result = await purchaseSeat(selectedSeatId, sessionId.current);
      const ticketDetails = await getTicket(result.ticket_code);
      setSelectedSeatId(null);
      setTicket(ticketDetails);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusySeatId(null);
    }
  };

  if (ticket) return <main className="app-shell"><Ticket ticket={ticket} onClose={() => setTicket(null)} /></main>;

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Live event ticketing</p>
          <h1>Choose your place in the room</h1>
          <p className="hero__description">
            Select an available seat. Changes made by other visitors appear instantly.
          </p>
        </div>
        <span className={`connection connection--${connection}`} aria-live="polite">
          <span />{connection === "connected" ? "Live updates" : "Reconnecting"}
        </span>
      </header>

      <StatusLegend />

      {error && <div className="alert" role="alert">{error}</div>}

      {loading ? (
        <div className="loading">Loading seats...</div>
      ) : seats.length === 0 ? (
        <div className="empty-state">No seats are available for this hall.</div>
      ) : (
        <SeatMap
          seats={seats}
          selectedSeatId={selectedSeatId}
          busySeatId={busySeatId}
          onSelect={handleSeatSelection}
        />
      )}

      <footer className="selection-bar">
        <div>
          <span>Your selection</span>
          <strong>{selectedSeat ? `${selectedSeat.row}${selectedSeat.number}` : "No seat selected"}</strong>
        </div>
        <button
          className="button"
          type="button"
          disabled={!selectedSeat || busySeatId !== null}
          onClick={handlePurchase}
        >
          {busySeatId !== null && busySeatId === selectedSeatId
            ? "Processing..."
            : "Confirm purchase"}
        </button>
      </footer>
    </main>
  );
}
