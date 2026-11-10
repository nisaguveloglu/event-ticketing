import Seat from "../Seat/Seat";

function groupSeatsByRow(seats) {
  return seats.reduce((rows, seat) => {
    const row = rows.get(seat.row) || [];
    row.push(seat);
    rows.set(seat.row, row);
    return rows;
  }, new Map());
}

export default function SeatMap({ seats, selectedSeatId, busySeatId, onSelect }) {
  const rows = [...groupSeatsByRow(seats).entries()].sort(([a], [b]) =>
    a.localeCompare(b),
  );

  return (
    <section className="seat-map" aria-labelledby="seat-map-title">
      <div className="screen" aria-hidden="true">
        <span>STAGE</span>
      </div>
      <h2 id="seat-map-title" className="visually-hidden">Choose a seat</h2>
      <div className="seat-map__rows">
        {rows.map(([rowName, rowSeats]) => (
          <div className="seat-row" key={rowName}>
            <span className="seat-row__label">{rowName}</span>
            <div className="seat-row__seats">
              {rowSeats
                .sort((a, b) => a.number - b.number)
                .map((seat) => (
                  <Seat
                    key={seat.id}
                    seat={seat}
                    displayStatus={seat.id === selectedSeatId ? "SELECTED" : seat.status}
                    busy={seat.id === busySeatId}
                    onSelect={onSelect}
                  />
                ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
