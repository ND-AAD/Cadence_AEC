import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChangeItemView } from "../ChangeItemView";
import { buildItem } from "@/test/helpers";
import { acknowledgeChange, startReview, holdItem, resumeReview } from "@/api/workflow";

vi.mock("@/api/workflow", () => ({
  acknowledgeChange: vi.fn(() => Promise.resolve()),
  startReview: vi.fn(() => Promise.resolve()),
  holdItem: vi.fn(() => Promise.resolve()),
  resumeReview: vi.fn(() => Promise.resolve()),
}));

vi.mock("@/components/story/ItemNotes", () => ({
  ItemNotes: () => <div data-testid="item-notes" />,
}));

const defaultProps = {
  onNavigate: vi.fn(),
  onWorkflowAction: vi.fn(),
};

function makeItem(status = "detected") {
  return buildItem({
    item_type: "change",
    identifier: "Schedule / Door 101 / DD\u2192CD",
    properties: {
      status,
      property_name: "finish",
      previous_value: "paint",
      new_value: "stain",
    },
  });
}

describe("ChangeItemView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders change header with property display name", () => {
    const item = makeItem();
    render(
      <ChangeItemView
        item={item}
        propertyName="Fire Rating"
        fromContextName="DD"
        toContextName="CD"
        {...defaultProps}
      />
    );
    expect(screen.getByText("Fire Rating")).toBeInTheDocument();
    expect(screen.getByText("CHANGE")).toBeInTheDocument();
  });

  it("falls back to item.properties.property_name when propertyName prop absent", () => {
    const item = makeItem();
    render(
      <ChangeItemView item={item} {...defaultProps} />
    );
    // displayProperty falls back to item.properties.property_name = "finish"
    expect(screen.getByText("finish")).toBeInTheDocument();
  });

  it("shows old and new values when context names and values provided", () => {
    const item = makeItem();
    render(
      <ChangeItemView
        item={item}
        fromContextName="DD"
        toContextName="CD"
        oldValue="paint"
        newValue="stain"
        {...defaultProps}
      />
    );
    expect(screen.getByText("paint")).toBeInTheDocument();
    expect(screen.getByText("stain")).toBeInTheDocument();
    expect(screen.getByText("DD")).toBeInTheDocument();
    expect(screen.getByText("CD")).toBeInTheDocument();
  });

  it("shows Start Review button at detected status", () => {
    const item = makeItem("detected");
    render(
      <ChangeItemView item={item} {...defaultProps} />
    );
    expect(screen.getByRole("button", { name: "Start Review" })).toBeInTheDocument();
  });

  it("Start Review calls startReview API with item id", async () => {
    const user = userEvent.setup();
    const item = makeItem("detected");
    render(
      <ChangeItemView item={item} {...defaultProps} />
    );
    await user.click(screen.getByRole("button", { name: "Start Review" }));

    await waitFor(() => {
      expect(startReview).toHaveBeenCalledWith(item.id);
    });
  });

  it("Acknowledge calls acknowledgeChange API and fires onWorkflowAction", async () => {
    const user = userEvent.setup();
    const item = makeItem("detected");
    const onWorkflowAction = vi.fn();
    render(
      <ChangeItemView item={item} {...defaultProps} onWorkflowAction={onWorkflowAction} />
    );
    await user.click(screen.getByRole("button", { name: "Acknowledge" }));

    await waitFor(() => {
      expect(acknowledgeChange).toHaveBeenCalledWith(item.id);
      expect(onWorkflowAction).toHaveBeenCalled();
    });
  });

  it("Hold calls holdItem API", async () => {
    const user = userEvent.setup();
    const item = makeItem("in_review");
    render(
      <ChangeItemView item={item} {...defaultProps} />
    );
    await user.click(screen.getByRole("button", { name: "Hold" }));

    await waitFor(() => {
      expect(holdItem).toHaveBeenCalledWith(item.id);
    });
  });

  it("Resume Review visible only at hold status", () => {
    const heldItem = makeItem("hold");
    const { unmount } = render(
      <ChangeItemView item={heldItem} {...defaultProps} />
    );
    expect(screen.getByRole("button", { name: "Resume Review" })).toBeInTheDocument();
    unmount();

    const detectedItem = makeItem("detected");
    render(
      <ChangeItemView item={detectedItem} {...defaultProps} />
    );
    expect(screen.queryByRole("button", { name: "Resume Review" })).not.toBeInTheDocument();
  });

  it("Resume Review calls resumeReview API", async () => {
    const user = userEvent.setup();
    const item = makeItem("hold");
    render(
      <ChangeItemView item={item} {...defaultProps} />
    );
    await user.click(screen.getByRole("button", { name: "Resume Review" }));

    await waitFor(() => {
      expect(resumeReview).toHaveBeenCalledWith(item.id);
    });
  });

  it("renders error message on API failure", async () => {
    vi.mocked(acknowledgeChange).mockRejectedValueOnce(new Error("Network error"));
    const user = userEvent.setup();
    const item = makeItem("detected");
    render(
      <ChangeItemView item={item} {...defaultProps} />
    );
    await user.click(screen.getByRole("button", { name: "Acknowledge" }));

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("hides action buttons when status is acknowledged", () => {
    const item = makeItem("acknowledged");
    render(
      <ChangeItemView item={item} {...defaultProps} />
    );
    expect(screen.queryByRole("button", { name: "Start Review" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Hold" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resume Review" })).not.toBeInTheDocument();
    // Shows acknowledged badge instead
    expect(screen.getByText("Acknowledged")).toBeInTheDocument();
  });
});
