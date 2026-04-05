// ─── ChangeItemsExpansion tests ───────────────────────────────────
// Covers the Acknowledge button: present when onAcknowledge is provided,
// absent when undefined, and calls onAcknowledge with the correct change ID.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChangeItemsExpansion } from "@/components/story/ChangeItemsExpansion";

// Mock the items API to return controlled change data.
vi.mock("@/api/items", () => ({
  getItems: vi.fn(),
}));

import { getItems } from "@/api/items";

const mockGetItems = getItems as ReturnType<typeof vi.fn>;

const fakeChangeItem = {
  id: "change-001",
  item_type: "change",
  identifier: null,
  properties: {
    changes: {
      fire_rating: { old: "45 min", new: "60 min" },
    },
    from_context_name: "DD",
    to_context_name: "CD",
    source_name: "Door Schedule",
  },
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("ChangeItemsExpansion", () => {
  beforeEach(() => {
    mockGetItems.mockResolvedValue([fakeChangeItem]);
  });

  it("renders Acknowledge button when onAcknowledge is provided", async () => {
    render(
      <ChangeItemsExpansion
        changeIds={["change-001"]}
        propertyName="fire_rating"
        onNavigate={vi.fn()}
        onAcknowledge={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /acknowledge/i })).toBeInTheDocument();
    });
  });

  it("does NOT render Acknowledge button when onAcknowledge is undefined", async () => {
    render(
      <ChangeItemsExpansion
        changeIds={["change-001"]}
        propertyName="fire_rating"
        onNavigate={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("60 min")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: /acknowledge/i })).not.toBeInTheDocument();
  });

  it("clicking Acknowledge calls onAcknowledge with the change item ID", async () => {
    const user = userEvent.setup();
    const onAcknowledge = vi.fn();

    render(
      <ChangeItemsExpansion
        changeIds={["change-001"]}
        propertyName="fire_rating"
        onNavigate={vi.fn()}
        onAcknowledge={onAcknowledge}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /acknowledge/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /acknowledge/i }));
    expect(onAcknowledge).toHaveBeenCalledTimes(1);
    expect(onAcknowledge).toHaveBeenCalledWith("change-001");
  });

  it("renders old and new values from the changes dict", async () => {
    render(
      <ChangeItemsExpansion
        changeIds={["change-001"]}
        propertyName="fire_rating"
        onNavigate={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("45 min")).toBeInTheDocument();
      expect(screen.getByText("60 min")).toBeInTheDocument();
    });
  });

  it("renders context labels when available", async () => {
    render(
      <ChangeItemsExpansion
        changeIds={["change-001"]}
        propertyName="fire_rating"
        onNavigate={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText(/DD → CD/)).toBeInTheDocument();
    });
  });

  it("shows loading state initially", () => {
    // Don't resolve the promise yet.
    mockGetItems.mockReturnValue(new Promise(() => {}));

    render(
      <ChangeItemsExpansion
        changeIds={["change-001"]}
        propertyName="fire_rating"
        onNavigate={vi.fn()}
      />,
    );

    expect(screen.getByText(/loading changes/i)).toBeInTheDocument();
  });
});
