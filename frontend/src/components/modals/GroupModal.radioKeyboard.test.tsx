import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BUSINESS_GROUP_COLORS } from "../../erd/businessGroups";
import { GroupModal } from "./GroupModal";

afterEach(cleanup);

function RadioGroupHarness({ initialColor }: { initialColor: string }) {
  const [color, setColor] = useState(initialColor);

  return (
    <GroupModal
      isOpen
      businessGroups={[]}
      newGroupName=""
      setNewGroupName={vi.fn()}
      newGroupColor={color}
      setNewGroupColor={setColor}
      nodes={[]}
      onCloseGroupManager={vi.fn()}
      onCreateBusinessGroup={vi.fn()}
      onDeleteBusinessGroup={vi.fn()}
      onAssignBusinessGroup={vi.fn()}
    />
  );
}

function colorRadios(): HTMLElement[] {
  return screen.getAllByRole("radio", { name: /^색상 / });
}

describe("GroupModal color radio keyboard contract", () => {
  it("exposes the selected color as the only tabbable checked radio", () => {
    render(<RadioGroupHarness initialColor={BUSINESS_GROUP_COLORS[1]} />);

    expect(
      screen.getByRole("radiogroup", { name: "그룹 색상" }),
    ).toBeInTheDocument();

    const radios = colorRadios();
    expect(radios).toHaveLength(BUSINESS_GROUP_COLORS.length);
    expect(radios[1]).toHaveAttribute("aria-checked", "true");
    expect(radios[1]).toHaveAttribute("tabindex", "0");
    radios.forEach((radio, index) => {
      if (index === 1) return;
      expect(radio).toHaveAttribute("aria-checked", "false");
      expect(radio).toHaveAttribute("tabindex", "-1");
    });

    radios[1]!.focus();
    fireEvent.keyDown(radios[1]!, { key: "Enter" });
    expect(radios[1]).toHaveFocus();
    expect(radios[1]).toHaveAttribute("aria-checked", "true");
  });

  it("moves selection and focus with wrapping arrow-key navigation", () => {
    render(<RadioGroupHarness initialColor={BUSINESS_GROUP_COLORS[0]} />);

    let radios = colorRadios();
    radios[0]!.focus();
    fireEvent.keyDown(radios[0]!, { key: "ArrowLeft" });

    radios = colorRadios();
    expect(radios.at(-1)).toHaveFocus();
    expect(radios.at(-1)).toHaveAttribute("aria-checked", "true");
    expect(radios[0]).toHaveAttribute("aria-checked", "false");

    fireEvent.keyDown(radios.at(-1)!, { key: "ArrowDown" });

    radios = colorRadios();
    expect(radios[0]).toHaveFocus();
    expect(radios[0]).toHaveAttribute("aria-checked", "true");
  });

  it("keeps a deterministic tab stop when the supplied color is outside the palette", () => {
    render(<RadioGroupHarness initialColor="not-in-palette" />);

    let radios = colorRadios();
    expect(radios[0]).toHaveAttribute("tabindex", "0");
    expect(radios[0]).toHaveAttribute("aria-checked", "false");
    radios.slice(1).forEach((radio) => {
      expect(radio).toHaveAttribute("tabindex", "-1");
    });

    radios[0]!.focus();
    fireEvent.keyDown(radios[0]!, { key: "ArrowRight" });

    radios = colorRadios();
    expect(radios[1]).toHaveFocus();
    expect(radios[1]).toHaveAttribute("aria-checked", "true");
  });
});
