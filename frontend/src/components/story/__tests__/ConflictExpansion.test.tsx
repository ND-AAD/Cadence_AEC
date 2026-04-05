// ─── ConflictExpansion tests ──────────────────────────────────────
// Covers resolution flow: selecting a source calls onResolve with the
// correct sourceId (UUID, not display name), custom value uses
// manual_value method, and Resolve button is disabled when nothing selected.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  ConflictExpansion,
  type ConflictSource,
} from "@/components/story/ConflictExpansion";

const sources: ConflictSource[] = [
  { sourceId: "uuid-source-a", sourceName: "Door Schedule", value: "60 min" },
  { sourceId: "uuid-source-b", sourceName: "Finish Schedule", value: "45 min" },
];

describe("ConflictExpansion", () => {
  it("Resolve button is disabled when nothing is selected", () => {
    render(
      <ConflictExpansion
        propertyName="fire_rating"
        sources={sources}
        status="detected"
        onResolve={vi.fn()}
      />,
    );

    const resolveBtn = screen.getByRole("button", { name: /resolve/i });
    expect(resolveBtn).toBeDisabled();
  });

  it("selecting a source and clicking Resolve calls onResolve with correct sourceId", async () => {
    const user = userEvent.setup();
    const onResolve = vi.fn();

    render(
      <ConflictExpansion
        propertyName="fire_rating"
        sources={sources}
        status="detected"
        onResolve={onResolve}
      />,
    );

    // Select the first source radio button (Door Schedule).
    const radios = screen.getAllByRole("radio");
    await user.click(radios[0]);

    const resolveBtn = screen.getByRole("button", { name: /resolve/i });
    expect(resolveBtn).not.toBeDisabled();
    await user.click(resolveBtn);

    expect(onResolve).toHaveBeenCalledTimes(1);
    expect(onResolve).toHaveBeenCalledWith({
      chosen_value: "60 min",
      chosen_source_id: "uuid-source-a",
      method: "chosen_source",
    });
  });

  it("selecting custom value calls onResolve with method manual_value", async () => {
    const user = userEvent.setup();
    const onResolve = vi.fn();

    render(
      <ConflictExpansion
        propertyName="fire_rating"
        sources={sources}
        status="detected"
        onResolve={onResolve}
      />,
    );

    // Select the custom radio (third radio: after the two source radios).
    const radios = screen.getAllByRole("radio");
    await user.click(radios[2]); // custom radio

    // Type a custom value.
    const customInput = screen.getByPlaceholderText("Enter value…");
    await user.type(customInput, "90 min");

    const resolveBtn = screen.getByRole("button", { name: /resolve/i });
    await user.click(resolveBtn);

    expect(onResolve).toHaveBeenCalledWith({
      chosen_value: "90 min",
      chosen_source_id: null,
      method: "manual_value",
    });
  });

  it("Resolve button stays disabled for custom with empty text", async () => {
    const user = userEvent.setup();

    render(
      <ConflictExpansion
        propertyName="fire_rating"
        sources={sources}
        status="detected"
        onResolve={vi.fn()}
      />,
    );

    // Select the custom radio but leave input empty.
    const radios = screen.getAllByRole("radio");
    await user.click(radios[2]);

    const resolveBtn = screen.getByRole("button", { name: /resolve/i });
    expect(resolveBtn).toBeDisabled();
  });

  it("does not render resolution controls for resolved status", () => {
    render(
      <ConflictExpansion
        propertyName="fire_rating"
        sources={sources}
        status="resolved"
        onResolve={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: /resolve/i })).not.toBeInTheDocument();
  });

  it("does not render resolution controls when onResolve is not provided", () => {
    render(
      <ConflictExpansion
        propertyName="fire_rating"
        sources={sources}
        status="detected"
      />,
    );

    expect(screen.queryByRole("button", { name: /resolve/i })).not.toBeInTheDocument();
  });
});
