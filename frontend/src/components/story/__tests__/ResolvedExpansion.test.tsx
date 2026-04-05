// ─── ResolvedExpansion tests ──────────────────────────────────────
// Covers source value coloring (stamp vs redline-muted) based on
// whether the value matches the resolution, and directive sub-row
// rendering.

import { render, screen } from "@testing-library/react";
import {
  ResolvedExpansion,
  type ResolvedSource,
  type ResolvedDirective,
} from "@/components/story/ResolvedExpansion";

// Mock child components to isolate unit behavior.
vi.mock("@/components/story/ResolutionStamp", () => ({
  ResolutionStamp: (props: { chosenValue: string }) => (
    <div data-testid="resolution-stamp">{props.chosenValue}</div>
  ),
}));

vi.mock("@/components/story/DirectiveSubRow", () => ({
  DirectiveSubRow: (props: { targetSourceName: string; status: string }) => (
    <div data-testid="directive-sub-row">
      {props.targetSourceName} - {props.status}
    </div>
  ),
}));

const baseSources: ResolvedSource[] = [
  { sourceId: "s1", sourceName: "Door Schedule", value: "60 min", isChosen: true },
  { sourceId: "s2", sourceName: "Finish Schedule", value: "45 min", isChosen: false },
];

describe("ResolvedExpansion", () => {
  it("applies stamp color to source whose value matches resolution", () => {
    const { container } = render(
      <ResolvedExpansion
        propertyName="fire_rating"
        itemType="conflict"
        sources={baseSources}
        resolution={{ chosenValue: "60 min" }}
      />,
    );

    // Find the source name spans — first source matches resolution
    const sourceNameSpans = container.querySelectorAll(
      ".grid > span:first-child",
    );
    expect(sourceNameSpans[0].className).toContain("text-stamp");
    expect(sourceNameSpans[1].className).toContain("text-redline/50");
  });

  it("applies stamp color to source value text matching resolution", () => {
    const { container } = render(
      <ResolvedExpansion
        propertyName="fire_rating"
        itemType="conflict"
        sources={baseSources}
        resolution={{ chosenValue: "60 min" }}
      />,
    );

    // Value spans are the second child in each grid row
    const valueSpans = container.querySelectorAll(
      ".grid > span:last-child",
    );
    expect(valueSpans[0].className).toContain("text-stamp");
    expect(valueSpans[1].className).toContain("text-redline/50");
  });

  it("applies redline-muted to BOTH sources when custom resolution matches neither", () => {
    const { container } = render(
      <ResolvedExpansion
        propertyName="fire_rating"
        itemType="conflict"
        sources={baseSources}
        resolution={{ chosenValue: "90 min" }}
      />,
    );

    const sourceNameSpans = container.querySelectorAll(
      ".grid > span:first-child",
    );
    expect(sourceNameSpans[0].className).toContain("text-redline/50");
    expect(sourceNameSpans[1].className).toContain("text-redline/50");
  });

  it("renders directive sub-rows with pending status", () => {
    const directives: ResolvedDirective[] = [
      {
        directiveId: "d1",
        targetSourceName: "Finish Schedule",
        propertyName: "fire_rating",
        targetValue: "60 min",
        status: "pending",
      },
    ];

    render(
      <ResolvedExpansion
        propertyName="fire_rating"
        itemType="conflict"
        sources={baseSources}
        resolution={{ chosenValue: "60 min" }}
        directives={directives}
      />,
    );

    const subRow = screen.getByTestId("directive-sub-row");
    expect(subRow).toHaveTextContent("Finish Schedule");
    expect(subRow).toHaveTextContent("pending");
  });

  it("renders resolution stamp with chosen value", () => {
    render(
      <ResolvedExpansion
        propertyName="fire_rating"
        itemType="conflict"
        sources={baseSources}
        resolution={{ chosenValue: "60 min", chosenSourceName: "Door Schedule" }}
      />,
    );

    const stamp = screen.getByTestId("resolution-stamp");
    expect(stamp).toHaveTextContent("60 min");
  });

  it("shows CHANGE type label for change items", () => {
    render(
      <ResolvedExpansion
        propertyName="material"
        itemType="change"
        fromContextName="DD"
        toContextName="CD"
        resolution={{ chosenValue: "Steel" }}
      />,
    );

    expect(screen.getByText("CHANGE")).toBeInTheDocument();
    expect(screen.getByText("DD → CD")).toBeInTheDocument();
  });
});
