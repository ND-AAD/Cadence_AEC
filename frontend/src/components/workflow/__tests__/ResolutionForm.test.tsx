import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResolutionForm } from "../ResolutionForm";
import { buildSource } from "@/test/helpers";

const sourceA = buildSource({ sourceName: "Finish Schedule", value: "60 min", sourceId: "src-a" });
const sourceB = buildSource({ sourceName: "Door Schedule", value: "90 min", sourceId: "src-b" });
const defaultSources = [sourceA, sourceB];

describe("ResolutionForm", () => {
  it("renders source radio buttons from sources prop", () => {
    render(
      <ResolutionForm sources={defaultSources} status="detected" />
    );
    expect(screen.getByText("Finish Schedule")).toBeInTheDocument();
    expect(screen.getByText("60 min")).toBeInTheDocument();
    expect(screen.getByText("Door Schedule")).toBeInTheDocument();
    expect(screen.getByText("90 min")).toBeInTheDocument();
  });

  it("selecting a source enables Resolve button", async () => {
    const user = userEvent.setup();
    render(
      <ResolutionForm
        sources={defaultSources}
        status="detected"
        onResolve={vi.fn()}
      />
    );
    const resolveBtn = screen.getByRole("button", { name: /^Resolve$/ });
    expect(resolveBtn).toBeDisabled();

    await user.click(screen.getByText("Finish Schedule"));
    expect(resolveBtn).toBeEnabled();
  });

  it("Resolve button disabled when no selection", () => {
    render(
      <ResolutionForm
        sources={defaultSources}
        status="detected"
        onResolve={vi.fn()}
      />
    );
    const resolveBtn = screen.getByRole("button", { name: /^Resolve$/ });
    expect(resolveBtn).toBeDisabled();
  });

  it("custom value toggle shows text input and enables resolve", async () => {
    const user = userEvent.setup();
    render(
      <ResolutionForm
        sources={defaultSources}
        status="detected"
        onResolve={vi.fn()}
      />
    );
    const resolveBtn = screen.getByRole("button", { name: /^Resolve$/ });

    await user.click(screen.getByText("custom value"));
    expect(resolveBtn).toBeDisabled();

    const input = screen.getByPlaceholderText("Enter value…");
    await user.type(input, "75 min");
    expect(resolveBtn).toBeEnabled();
  });

  it("resolve with selected source fires onResolve with correct payload", async () => {
    const user = userEvent.setup();
    const onResolve = vi.fn();
    render(
      <ResolutionForm
        sources={defaultSources}
        status="detected"
        onResolve={onResolve}
      />
    );

    await user.click(screen.getByText("Finish Schedule"));
    const rationaleInput = screen.getByPlaceholderText("Field measurement confirms value per code…");
    await user.type(rationaleInput, "Per field check");
    const decidedByInput = screen.getByPlaceholderText("J. Martinez");
    await user.type(decidedByInput, "A. Smith");

    await user.click(screen.getByRole("button", { name: /^Resolve$/ }));

    expect(onResolve).toHaveBeenCalledWith({
      chosen_value: "60 min",
      chosen_source_id: "src-a",
      method: "chosen_source",
      rationale: "Per field check",
      decided_by: "A. Smith",
      note: undefined,
    });
  });

  it("resolve with custom value fires onResolve with correct payload", async () => {
    const user = userEvent.setup();
    const onResolve = vi.fn();
    render(
      <ResolutionForm
        sources={defaultSources}
        status="detected"
        onResolve={onResolve}
      />
    );

    await user.click(screen.getByText("custom value"));
    await user.type(screen.getByPlaceholderText("Enter value…"), "75 min");

    await user.click(screen.getByRole("button", { name: /^Resolve$/ }));

    expect(onResolve).toHaveBeenCalledWith({
      chosen_value: "75 min",
      chosen_source_id: null,
      method: "manual_value",
      rationale: "",
      decided_by: "",
      note: undefined,
    });
  });

  it("Start Review button visible only when status=detected", () => {
    const onStartReview = vi.fn();

    const { unmount } = render(
      <ResolutionForm
        sources={defaultSources}
        status="detected"
        onStartReview={onStartReview}
      />
    );
    expect(screen.getByRole("button", { name: /Start Review/ })).toBeInTheDocument();
    unmount();

    render(
      <ResolutionForm
        sources={defaultSources}
        status="in_review"
        onStartReview={onStartReview}
      />
    );
    expect(screen.queryByRole("button", { name: /Start Review/ })).not.toBeInTheDocument();
  });

  it("Hold button visible when status is active (detected or in_review)", () => {
    const onHold = vi.fn();

    const { unmount: u1 } = render(
      <ResolutionForm sources={defaultSources} status="detected" onHold={onHold} />
    );
    expect(screen.getByRole("button", { name: /^Hold/ })).toBeInTheDocument();
    u1();

    const { unmount: u2 } = render(
      <ResolutionForm sources={defaultSources} status="in_review" onHold={onHold} />
    );
    expect(screen.getByRole("button", { name: /^Hold/ })).toBeInTheDocument();
    u2();

    render(
      <ResolutionForm sources={defaultSources} status="hold" onHold={onHold} />
    );
    expect(screen.queryByRole("button", { name: /^Hold/ })).not.toBeInTheDocument();
  });

  it("Resume button visible only when status=hold", () => {
    const onResume = vi.fn();

    const { unmount } = render(
      <ResolutionForm sources={defaultSources} status="hold" onResume={onResume} />
    );
    expect(screen.getByRole("button", { name: /Resume Review/ })).toBeInTheDocument();
    unmount();

    render(
      <ResolutionForm sources={defaultSources} status="detected" onResume={onResume} />
    );
    expect(screen.queryByRole("button", { name: /Resume Review/ })).not.toBeInTheDocument();
  });

  it("Hold button calls onHold", async () => {
    const user = userEvent.setup();
    const onHold = vi.fn();
    render(
      <ResolutionForm sources={defaultSources} status="detected" onHold={onHold} />
    );
    await user.click(screen.getByRole("button", { name: /^Hold/ }));
    expect(onHold).toHaveBeenCalledOnce();
  });

  it("Start Review calls onStartReview", async () => {
    const user = userEvent.setup();
    const onStartReview = vi.fn();
    render(
      <ResolutionForm
        sources={defaultSources}
        status="detected"
        onStartReview={onStartReview}
      />
    );
    await user.click(screen.getByRole("button", { name: /Start Review/ }));
    expect(onStartReview).toHaveBeenCalledOnce();
  });

  it("note field included in resolve payload when filled", async () => {
    const user = userEvent.setup();
    const onResolve = vi.fn();
    render(
      <ResolutionForm
        sources={defaultSources}
        status="detected"
        onResolve={onResolve}
      />
    );

    await user.click(screen.getByText("Finish Schedule"));
    const noteArea = screen.getByPlaceholderText("Notes persist independently of resolution status.");
    await user.type(noteArea, "Check with architect");
    await user.click(screen.getByRole("button", { name: /^Resolve$/ }));

    expect(onResolve).toHaveBeenCalledWith(
      expect.objectContaining({ note: "Check with architect" })
    );
  });
});
