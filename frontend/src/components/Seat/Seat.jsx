const STATUS_LABELS = {
  AVAILABLE: "Available",
  SELECTED: "Selected by you",
  LOCKED: "Locked",
  SOLD: "Sold",
};

export default function Seat({ seat, displayStatus, busy, onSelect }) {
  const disabled = busy || displayStatus === "LOCKED" || displayStatus === "SOLD";
  const label = `${seat.row}${seat.number}, ${STATUS_LABELS[displayStatus]}`;

  return (
    <button
      type="button"
      className={`seat seat--${displayStatus.toLowerCase()}`}
      aria-label={label}
      aria-pressed={displayStatus === "SELECTED"}
      disabled={disabled}
      onClick={() => onSelect(seat)}
    >
      <span>{seat.row}{seat.number}</span>
    </button>
  );
}
