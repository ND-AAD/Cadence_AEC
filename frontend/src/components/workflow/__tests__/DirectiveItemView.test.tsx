import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DirectiveItemView } from "../DirectiveItemView";
import { buildItem } from "@/test/helpers";

vi.mock("@/api/workflow", () => ({
  holdItem: vi.fn(() => Promise.resolve()),
  resumeReview: vi.fn(() => Promise.resolve()),
}));
vi.mock("@/api/actionItems", () => ({
  fulfillDirective: vi.fn(() => Promise.resolve()),
}));
vi.mock("@/components/story/ItemNotes", () => ({
  ItemNotes: () => <div data-testid="item-notes" />,
}));

import { holdItem, resumeReview } from "@/api/workflow";
import { fulfillDirective } from "@/api/actionItems";

function makeDirective(status = "pending") {
  return buildItem({
    item_type: "directive",
    identifier: "Update finish to stain",
    properties: {
      status,
      property_name: "finish",
      target_value: "stain",
      target_source: "some-uuid",
    },
  });
}

describe("DirectiveItemView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders directive header with property name", () => {
    const item = makeDirective();
    render(
      <DirectiveItemView
        item={item}
        propertyName="Finish"
        onNavigate={vi.fn()}
      />
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Finish");
    expect(screen.getByText("DIRECTIVE")).toBeInTheDocument();
  });

  it("shows obligation text with target source, property, and value", () => {
    const item = makeDirective();
    render(
      <DirectiveItemView
        item={item}
        targetSourceName="Finish Schedule"
        propertyName="Fire Rating"
        targetValue="60 min"
        onNavigate={vi.fn()}
      />
    );
    expect(screen.getByText("Finish Schedule")).toBeInTheDocument();
    // Property name appears in header AND obligation — use getAllByText
    expect(screen.getAllByText("Fire Rating")).toHaveLength(2);
    expect(screen.getByText("60 min")).toBeInTheDocument();
  });

  it("affected item link navigates on click", async () => {
    const user = userEvent.setup();
    const item = makeDirective();
    const onNavigate = vi.fn();
    render(
      <DirectiveItemView
        item={item}
        affectedItemId="item-123"
        affectedItemName="Door 101"
        onNavigate={onNavigate}
      />
    );
    await user.click(screen.getByText("Door 101"));
    expect(onNavigate).toHaveBeenCalledWith("item-123");
  });

  it("decision link navigates on click", async () => {
    const user = userEvent.setup();
    const item = makeDirective();
    const onNavigate = vi.fn();
    render(
      <DirectiveItemView
        item={item}
        decisionId="dec-456"
        decisionName="Fire Rating Resolution"
        onNavigate={onNavigate}
      />
    );
    await user.click(screen.getByText("Fire Rating Resolution"));
    expect(onNavigate).toHaveBeenCalledWith("dec-456");
  });

  it("shows Mark Fulfilled button at pending status", () => {
    const item = makeDirective("pending");
    render(
      <DirectiveItemView item={item} onNavigate={vi.fn()} />
    );
    expect(screen.getByRole("button", { name: "Mark Fulfilled" })).toBeInTheDocument();
  });

  it("Mark Fulfilled calls fulfillDirective API then onWorkflowAction", async () => {
    const user = userEvent.setup();
    const item = makeDirective("pending");
    const onWorkflowAction = vi.fn();
    render(
      <DirectiveItemView
        item={item}
        onNavigate={vi.fn()}
        onWorkflowAction={onWorkflowAction}
      />
    );
    await user.click(screen.getByRole("button", { name: "Mark Fulfilled" }));
    await waitFor(() => {
      expect(fulfillDirective).toHaveBeenCalledWith(item.id);
    });
    await waitFor(() => {
      expect(onWorkflowAction).toHaveBeenCalled();
    });
  });

  it("Hold calls holdItem API", async () => {
    const user = userEvent.setup();
    const item = makeDirective("pending");
    const onWorkflowAction = vi.fn();
    render(
      <DirectiveItemView
        item={item}
        onNavigate={vi.fn()}
        onWorkflowAction={onWorkflowAction}
      />
    );
    await user.click(screen.getByRole("button", { name: "Hold" }));
    await waitFor(() => {
      expect(holdItem).toHaveBeenCalledWith(item.id);
    });
    await waitFor(() => {
      expect(onWorkflowAction).toHaveBeenCalled();
    });
  });

  it("Resume visible only at hold status", () => {
    const holdItem = makeDirective("hold");
    const { unmount } = render(
      <DirectiveItemView item={holdItem} onNavigate={vi.fn()} />
    );
    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark Fulfilled" })).not.toBeInTheDocument();
    unmount();

    const pendingItem = makeDirective("pending");
    render(
      <DirectiveItemView item={pendingItem} onNavigate={vi.fn()} />
    );
    expect(screen.queryByRole("button", { name: "Resume" })).not.toBeInTheDocument();
  });

  it("Resume calls resumeReview API", async () => {
    const user = userEvent.setup();
    const item = makeDirective("hold");
    const onWorkflowAction = vi.fn();
    render(
      <DirectiveItemView
        item={item}
        onNavigate={vi.fn()}
        onWorkflowAction={onWorkflowAction}
      />
    );
    await user.click(screen.getByRole("button", { name: "Resume" }));
    await waitFor(() => {
      expect(resumeReview).toHaveBeenCalledWith(item.id);
    });
    await waitFor(() => {
      expect(onWorkflowAction).toHaveBeenCalled();
    });
  });

  it("fulfilled status hides action buttons", () => {
    const item = makeDirective("fulfilled");
    render(
      <DirectiveItemView item={item} onNavigate={vi.fn()} />
    );
    expect(screen.queryByRole("button", { name: "Mark Fulfilled" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Hold" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resume" })).not.toBeInTheDocument();
    // Fulfilled text appears in status label and badge
    expect(screen.getAllByText("Fulfilled")).toHaveLength(2);
  });

  it("error state renders on API failure", async () => {
    const user = userEvent.setup();
    vi.mocked(fulfillDirective).mockRejectedValueOnce(new Error("Network error"));
    const item = makeDirective("pending");
    render(
      <DirectiveItemView item={item} onNavigate={vi.fn()} />
    );
    await user.click(screen.getByRole("button", { name: "Mark Fulfilled" }));
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });
});
