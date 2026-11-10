const ITEMS = [
  ["AVAILABLE", "Available"],
  ["SELECTED", "Your selection"],
  ["LOCKED", "Locked"],
  ["SOLD", "Sold"],
];

export default function StatusLegend() {
  return (
    <ul className="legend" aria-label="Seat status legend">
      {ITEMS.map(([status, label]) => (
        <li key={status}>
          <span className={`legend__swatch legend__swatch--${status.toLowerCase()}`} />
          {label}
        </li>
      ))}
    </ul>
  );
}
