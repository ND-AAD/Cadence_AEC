import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildItem, buildSource } from "@/test/helpers";
import { ConflictItemView } from "../ConflictItemView";

// ── Mock API modules ──────────────────────────────────────────────

vi.mock("@/api/actionItems", () => ({
  resolveConflict: vi.fn(() => Promise.resolve()),
}));
vi.mock("@/api/workflow", () => ({
  startReview: vi.fn(() => Promise.resolve()),
  holdItem: vi.fn(() => Promise.resolve()),
  resumeReview: vi.fn(() => Promise.resolve()),
}));
vi.mock("@/api/notes", () => ({
  createNote: vi.fn(() => Promise.resolve()),
}));

// Mock ItemNotes — it fetches independently via useNotes
vi.mock("@/components/story/ItemNotes", () => ({
  ItemNotes: () => <div data-testid="item-notes" />,
}));

import { resolveConflict } from "@/api/actionItems";
import { startReview, holdItem } from "@/api/workflow";

// ── Test data ─────────────────────────────────────────────────────

const sourceA = buildSource({ sourceName: "Finish Schedule", value: "60 min", sourceId: "src-a" });
const sourceB = buildSource({ sourceName: "Door Schedule", value: "90 min", sourceId: "src-b" });
const defaultSources = [sourceA, sourceB];

function buildConflictItem(overrides: Record<string, unknown> = {}) {
  return buildItem({
    item_type: "conflict",
    identifier: "Door 101 / finish / Schedule\u00d7Spec",
    properties: {
      status: "detected",
      property_name: "finish",
      ...((overrides.properties as Record<string, unknown>) ?? {}),
    },
    ...overrides,
  });
}

describe("ConflictItemView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // 1. Renders conflict header with property name and status
  it("renders conflict header with property name and status", () => {
    const item = buildConflictItem();
    render(
      <ConflictItemView
        item={item}
        sources={defaultSources}
        onNavigate={vi.fn()}
      />
    );

    // Header h1 shows property name
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("finish");
    // Status badge shows "CONFLICT" and the UX label
    expect(screen.getByText("CONFLICT")).toBeInTheDocument();
    expect(screen.getByText("Needs Review")).toBeInTheDocument();
  });

  // 2. Shows source values in disagreement display
  it("shows source values in disagreement display", () => {
    const item = buildConflictItem();
    render(
      <ConflictItemView
        item={item}
        sources={defaultSources}
        onNavigate={vi.fn()}
      />
    );

    // Source names appear as navigable buttons in the column headers
    const sourceButtons = screen.getAllByRole("button").filter(
      (b) => b.getAttribute("title")?.startsWith("Navigate to")
    );
    expect(sourceButtons).toHaveLength(2);
    expect(sourceButtons[0]).toHaveTextContent("Finish Schedule");
    expect(sourceButtons[1]).toHaveTextContent("Door Schedule");

    // Values appear in the value row
    expect(screen.getAllByText("60 min").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("90 min").length).toBeGreaterThanOrEqual(1);
  });

  // 3. Source names are navigable
  it("source names call onNavigate with source ID when clicked", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const item = buildConflictItem();
    render(
      <ConflictItemView
        item={item}
        sources={defaultSources}
        onNavigate={onNavigate}
      />
    );

    // Click the source header buttons (Navigate to ...)
    const sourceButtons = screen.getAllByRole("button").filter(
      (b) => b.getAttribute("title")?.startsWith("Navigate to")
    );
    await user.click(sourceButtons[0]);
    expect(onNavigate).toHaveBeenCalledWith("src-a");

    await user.click(sourceButtons[1]);
    expect(onNavigate).toHaveBeenCalledWith("src-b");
  });

  // 4. ResolutionForm receives sources and renders radio buttons
  it("renders source radio buttons from ResolutionForm", () => {
    const item = buildConflictItem();
    render(
      <ConflictItemView
        item={item}
        sources={defaultSources}
        onNavigate={vi.fn()}
      />
    );

    // Radio buttons rendered by ResolutionForm: 2 sources + 1 custom = 3
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(3);
  });

  // 5. Resolve calls resolveConflict API then onWorkflowAction
  it("resolve calls resolveConflict API then onWorkflowAction", async () => {
    const user = userEvent.setup();
    const onWorkflowAction = vi.fn();
    const item = buildConflictItem({ id: "conflict-123" });
    render(
      <ConflictItemView
        item={item}
        sources={defaultSources}
        onNavigate={vi.fn()}
        onWorkflowAction={onWorkflowAction}
      />
    );

    // Select first source via its radio label text in the ResolutionForm
    // The ResolutionForm has labels with source name spans — click the radio for src-a
    const radios = screen.getAllByRole("radio");
    await user.click(radios[0]); // First source radio

    // Click Resolve button
    await user.click(screen.getByRole("button", { name: /^Resolve/ }));

    await waitFor(() => {
      expect(resolveConflict).toHaveBeenCalledWith("conflict-123", {
        chosen_value: "60 min",
        chosen_source_id: "src-a",
        method: "chosen_source",
        rationale: "",
        decided_by: "",
      });
    });

    await waitFor(() => {
      expect(onWorkflowAction).toHaveBeenCalledOnce();
    });
  });

  // 6. Start Review calls startReview API
  it("Start Review calls startReview API", async () => {
    const user = userEvent.setup();
    const onWorkflowAction = vi.fn();
    const item = buildConflictItem({ id: "conflict-456" });
    render(
      <ConflictItemView
        item={item}
        sources={defaultSources}
        onNavigate={vi.fn()}
        onWorkflowAction={onWorkflowAction}
      />
    );

    await user.click(screen.getByRole("button", { name: /Start Review/ }));

    await waitFor(() => {
      expect(startReview).toHaveBeenCalledWith("conflict-456");
    });
    await waitFor(() => {
      expect(onWorkflowAction).toHaveBeenCalledOnce();
    });
  });

  // 7. Hold calls holdItem API
  it("Hold calls holdItem API", async () => {
    const user = userEvent.setup();
    const onWorkflowAction = vi.fn();
    const item = buildConflictItem({ id: "conflict-789" });
    render(
      <ConflictItemView
        item={item}
        sources={defaultSources}
        onNavigate={vi.fn()}
        onWorkflowAction={onWorkflowAction}
      />
    );

    await user.click(screen.getByRole("button", { name: /^Hold/ }));

    await waitFor(() => {
      expect(holdItem).toHaveBeenCalledWith("conflict-789");
    });
    await waitFor(() => {
      expect(onWorkflowAction).toHaveBeenCalledOnce();
    });
  });

  // 8. Error state renders on API failure
  it("error state renders on API failure", async () => {
    const user = userEvent.setup();
    vi.mocked(resolveConflict).mockRejectedValueOnce(new Error("Server error"));
    const item = buildConflictItem();
    render(
      <ConflictItemView
        item={item}
        sources={defaultSources}
        onNavigate={vi.fn()}
      />
    );

    // Select source via radio and resolve
    const radios = screen.getAllByRole("radio");
    await user.click(radios[0]);
    await user.click(screen.getByRole("button", { name: /^Resolve/ }));

    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });

  // 9. Resolved state shows resolution stamp and hides form
  it("resolved state shows resolution stamp and hides resolve form", () => {
    const item = buildConflictItem({
      properties: { status: "resolved", property_name: "fire_rating" },
    });
    render(
      <ConflictItemView
        item={item}
        sources={defaultSources}
        resolution={{
          chosenValue: "60 min",
          chosenSourceId: "src-a",
          chosenSourceName: "Finish Schedule",
          decidedBy: "J. Martinez",
          method: "field verification",
          date: "2026-01-20",
        }}
        onNavigate={vi.fn()}
      />
    );

    // Resolution stamp is visible
    expect(screen.getByText("Resolved")).toBeInTheDocument();
    // The chosen value appears in the stamp (ResolutionStamp renders it)
    expect(screen.getByText(/from Finish Schedule/)).toBeInTheDocument();
    expect(screen.getByText(/J\. Martinez/)).toBeInTheDocument();

    // Status shows "Accepted" for resolved
    expect(screen.getByText("Accepted")).toBeInTheDocument();

    // Resolve form action buttons should not be present
    expect(screen.queryByRole("button", { name: /^Resolve/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Start Review/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Hold/ })).not.toBeInTheDocument();
  });

  // 10. Directive sub-rows render when directives provided
  it("directive sub-rows render when directives provided", () => {
    const item = buildConflictItem({
      properties: { status: "resolved", property_name: "fire_rating" },
    });
    render(
      <ConflictItemView
        item={item}
        sources={defaultSources}
        resolution={{
          chosenValue: "60 min",
          chosenSourceId: "src-a",
          chosenSourceName: "Finish Schedule",
        }}
        directives={[
          {
            directiveId: "dir-1",
            targetSourceName: "Door Schedule",
            propertyName: "fire_rating",
            targetValue: "60 min",
            status: "pending",
          },
          {
            directiveId: "dir-2",
            targetSourceName: "Hardware Schedule",
            propertyName: "fire_rating",
            targetValue: "60 min",
            status: "pending",
          },
        ]}
        onNavigate={vi.fn()}
      />
    );

    // Directives section header
    expect(screen.getByText("Directives")).toBeInTheDocument();
    // Directive target source names rendered via DirectiveSubRow
    expect(screen.getByText("Hardware Schedule")).toBeInTheDocument();
  });
});
