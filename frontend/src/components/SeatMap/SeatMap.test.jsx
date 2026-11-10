import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SeatMap from "./SeatMap";

const seats = [
  { id: 2, row: "A", number: 2, status: "LOCKED" },
  { id: 1, row: "A", number: 1, status: "AVAILABLE" },
  { id: 3, row: "B", number: 1, status: "SOLD" },
];

describe("SeatMap", () => {
  it("renders seats in row and number order", () => {
    render(<SeatMap seats={seats} selectedSeatId={null} onSelect={() => {}} />);
    expect(screen.getAllByRole("button").map((seat) => seat.textContent)).toEqual(["A1", "A2", "B1"]);
  });

  it("only allows selectable seats to be clicked", () => {
    const onSelect = vi.fn();
    render(<SeatMap seats={seats} selectedSeatId={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "A1, Available" }));
    expect(onSelect).toHaveBeenCalledWith(seats[1]);
    expect(screen.getByRole("button", { name: "A2, Locked" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "B1, Sold" })).toBeDisabled();
  });

  it("shows the current user's locked seat as selected", () => {
    render(<SeatMap seats={seats} selectedSeatId={2} onSelect={() => {}} />);
    expect(screen.getByRole("button", { name: "A2, Selected by you" })).toHaveAttribute("aria-pressed", "true");
  });
});
