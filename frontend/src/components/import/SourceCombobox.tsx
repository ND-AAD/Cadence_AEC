import { useState, useEffect, useRef } from "react";
import { apiGet, apiPost } from "@/api/client";

interface SourceItem {
  id: string;
  identifier: string;
  item_type: string;
  properties: Record<string, unknown>;
}

interface ConnectedGroup {
  item_type: string;
  items: SourceItem[];
}

interface SourceComboboxProps {
  projectId: string;
  value: { id: string; name: string } | null;
  onChange: (val: { id: string; name: string } | null) => void;
  /** Called when a new source is created (not selected). For cancel cleanup. */
  onItemCreated?: (id: string) => void;
}

const SOURCE_TYPES = [
  { value: "schedule", label: "Schedule" },
  { value: "specification", label: "Specification" },
  { value: "drawing", label: "Drawing" },
];

export function SourceCombobox({ projectId, value, onChange, onItemCreated }: SourceComboboxProps) {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [showTypeSelector, setShowTypeSelector] = useState(false);
  const [selectedType, setSelectedType] = useState("schedule");
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiGet<{ connected: ConnectedGroup[] }>(
          `/v1/items/${projectId}/connected`
        );
        const sourceTypes = ["schedule", "specification", "drawing", "source"];
        const items: SourceItem[] = [];
        for (const g of res.connected) {
          if (sourceTypes.includes(g.item_type)) {
            items.push(...g.items);
          }
        }
        setSources(items);
      } catch {
        // Silently fail
      }
    })();
  }, [projectId]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
        setShowTypeSelector(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = sources.filter((s) =>
    s.identifier.toLowerCase().includes(query.toLowerCase())
  );

  const exactMatch = sources.some(
    (s) => s.identifier.toLowerCase() === query.toLowerCase()
  );

  const showCreateOption = query.trim() && !exactMatch;
  const optionCount = filtered.length + (showCreateOption ? 1 : 0);

  async function handleCreate() {
    if (!query.trim() || creating) return;
    setCreating(true);
    try {
      const source = await apiPost<SourceItem>("/v1/items/", {
        item_type: selectedType,
        identifier: query.trim(),
        properties: {},
      });

      await apiPost("/v1/connections/", {
        source_item_id: projectId,
        target_item_id: source.id,
      });

      setSources((prev) => [...prev, source]);
      onChange({ id: source.id, name: source.identifier });
      onItemCreated?.(source.id);
      setQuery("");
      setOpen(false);
      setShowTypeSelector(false);
    } catch {
      // Handle error
    } finally {
      setCreating(false);
    }
  }

  function handleSelect(s: SourceItem) {
    onChange({ id: s.id, name: s.identifier });
    setQuery("");
    setOpen(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter") {
        setOpen(true);
        e.preventDefault();
      }
      return;
    }

    if (showTypeSelector) {
      // In type selector: Enter confirms creation
      if (e.key === "Enter") {
        e.preventDefault();
        handleCreate();
      } else if (e.key === "Escape") {
        setShowTypeSelector(false);
        e.preventDefault();
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightIndex((i) => (i + 1) % optionCount);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightIndex((i) => (i - 1 + optionCount) % optionCount);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlightIndex >= 0 && highlightIndex < filtered.length) {
        handleSelect(filtered[highlightIndex]);
      } else if (highlightIndex === filtered.length && showCreateOption) {
        setShowTypeSelector(true);
      } else if (optionCount === 1 && filtered.length === 1) {
        handleSelect(filtered[0]);
      } else if (optionCount === 1 && showCreateOption) {
        setShowTypeSelector(true);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      setHighlightIndex(-1);
    }
  }

  return (
    <div ref={wrapperRef} className="relative">
      <input
        type="text"
        value={value ? value.name : query}
        onChange={(e) => {
          if (value) onChange(null);
          setQuery(e.target.value);
          setOpen(true);
          setHighlightIndex(-1);
          setShowTypeSelector(false);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder="Type to search or create…"
        className="w-full px-3 py-2 text-sm bg-sheet border border-rule text-ink
                   focus:outline-none focus:border-ink transition-colors"
      />

      {open && (query || sources.length > 0) && (
        <div className="absolute z-10 mt-1 w-full bg-sheet border border-rule shadow-sm max-h-48 overflow-auto">
          {filtered.map((s, i) => (
            <button
              key={s.id}
              type="button"
              onClick={() => handleSelect(s)}
              className={`w-full text-left px-3 py-2 text-sm text-ink transition-colors ${
                i === highlightIndex ? "bg-vellum" : "hover:bg-vellum"
              }`}
            >
              {s.identifier}
              <span className="text-xs text-trace ml-2">{s.item_type}</span>
            </button>
          ))}
          {showCreateOption && !showTypeSelector && (
            <button
              type="button"
              onClick={() => setShowTypeSelector(true)}
              className={`w-full text-left px-3 py-2 text-sm text-ink transition-colors border-t border-rule ${
                highlightIndex === filtered.length ? "bg-vellum" : "hover:bg-vellum"
              }`}
            >
              Create "{query.trim()}"
            </button>
          )}
          {showCreateOption && showTypeSelector && (
            <div className="px-3 py-2 border-t border-rule">
              <p className="text-xs text-graphite mb-2">Source type:</p>
              <div className="flex gap-1 mb-2">
                {SOURCE_TYPES.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => setSelectedType(t.value)}
                    className={`px-2 py-1 text-xs transition-colors ${
                      selectedType === t.value
                        ? "bg-ink text-sheet"
                        : "text-graphite border border-rule hover:text-ink"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={handleCreate}
                disabled={creating}
                className="w-full px-2 py-1 text-xs font-medium bg-ink text-sheet hover:bg-ink/90 transition-colors disabled:opacity-50"
              >
                {creating ? "Creating…" : `Create ${selectedType}`}
              </button>
            </div>
          )}
          {filtered.length === 0 && !query.trim() && (
            <p className="px-3 py-2 text-xs text-trace">No sources yet — type to create one</p>
          )}
        </div>
      )}
    </div>
  );
}
