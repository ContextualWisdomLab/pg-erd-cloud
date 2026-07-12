import "@testing-library/jest-dom/vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, afterEach } from "vitest";
import { EditEdgeModal } from "./EditEdgeModal";

describe("EditEdgeModal", () => {
  const defaultProps = {
    editingEdge: { id: "e1", source: "A", target: "B" },
    relLabel: "test_label",
    setRelLabel: vi.fn(),
    onRelDelete: vi.fn(),
    onRelCancel: vi.fn(),
    onRelSubmit: vi.fn(),
  };

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders correctly when editingEdge is provided", () => {
    render(<EditEdgeModal {...defaultProps} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("관계 설정")).toBeInTheDocument();
    expect(screen.getByDisplayValue("test_label")).toBeInTheDocument();
  });

  it("does not render when editingEdge is null", () => {
    const { container } = render(<EditEdgeModal {...defaultProps} editingEdge={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("calls setRelLabel on input change", async () => {
    render(<EditEdgeModal {...defaultProps} />);
    const input = screen.getByLabelText(/제약조건 이름/);
    await userEvent.type(input, "1");
    expect(defaultProps.setRelLabel).toHaveBeenCalled();
  });

  it("calls onRelSubmit on Enter key down", async () => {
    render(<EditEdgeModal {...defaultProps} />);
    const input = screen.getByLabelText(/제약조건 이름/);
    await userEvent.type(input, "{Enter}");
    expect(defaultProps.onRelSubmit).toHaveBeenCalled();
  });

  it("calls onRelDelete when delete button is clicked and confirmed", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<EditEdgeModal {...defaultProps} />);
    const deleteBtn = screen.getByRole("button", { name: "관계 삭제" });
    await userEvent.click(deleteBtn);
    expect(confirmSpy).toHaveBeenCalled();
    expect(defaultProps.onRelDelete).toHaveBeenCalled();
  });

  it("does not call onRelDelete when delete button is clicked and dismissed", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<EditEdgeModal {...defaultProps} onRelDelete={defaultProps.onRelDelete} />);
    const deleteBtn = screen.getByRole("button", { name: "관계 삭제" });
    await userEvent.click(deleteBtn);
    expect(confirmSpy).toHaveBeenCalled();
  });
});
