import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { EditEdgeModal } from "./EditEdgeModal";

describe("EditEdgeModal", () => {
  it("submits the form natively with enter key", () => {
    const onRelSubmit = vi.fn();
    const setRelLabel = vi.fn();

    render(
      <EditEdgeModal
        editingEdge={{ id: "e1", source: "A", target: "B" }}
        relLabel=""
        setRelLabel={setRelLabel}
        onRelDelete={vi.fn()}
        onRelCancel={vi.fn()}
        onRelSubmit={onRelSubmit}
      />
    );

    const input = screen.getByLabelText("제약조건 이름 (Label)");
    fireEvent.change(input, { target: { value: "my_label" } });

    // Test that the input update was called
    expect(setRelLabel).toHaveBeenCalledWith("my_label");

    // Native submit via Enter on the form
    fireEvent.submit(screen.getByRole("dialog"));

    expect(onRelSubmit).toHaveBeenCalled();
  });

  it("does not render when editingEdge is null", () => {
    const { container } = render(
      <EditEdgeModal
        editingEdge={null}
        relLabel=""
        setRelLabel={vi.fn()}
        onRelDelete={vi.fn()}
        onRelCancel={vi.fn()}
        onRelSubmit={vi.fn()}
      />
    );
    expect(container.firstChild).toBeNull();
  });
});
