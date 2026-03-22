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
}

const SOURCE_TYPES = [
  { value: "schedule", label: "Schedule" },
  { value: "specification", label: "Specification" },
  { value: "drawing", label: "Drawing" },
];

export function SourceCombobox({ projectId, value, onChange }: SourceComboboxProps) {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [showTypeSelector, setShowTypeSelector] = useState(false);
  const [selectedType, setSelectedType] = useState("schedule");
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

  async function handleCreate() {
    if (!query.trim() || creating) return;
    setCreating(true);
    try {
      const source = await apiPost<SourceItem>("/v1/items", {
        item_type: selectedType,
        identifier: query.trim(),
        properties: {},
      });

      await apiPost("/v1/connections", {
        source_item_id: projectId,
        target_item_id: source.id,
      });

      setSources((prev) => [...prev, source]);
      onChange({ id: source.id, name: source.identifier });
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

  return (
    <div ref={wrapperRef} className="relative">
      <input
        type="text"
        value={value ? value.name : query}
        onChange={(e) => {
          if (value) onChange(null);
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder="Type to search or create…"
        className="w-full px-3 py-2 text-sm bg-sheet border border-rule text-ink
                   focus:outline-none focus:border-ink transition-colors"
      />

      {open && (query || sources.length > 0) && (
        <div className="absolute z-10 mt-1 w-full bg-sheet border border-rule shadow-sm max-h-48 overflow-auto">
          {filtered.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => handleSelect(s)}
              className="w-full text-left px-3 py-2 text-sm text-ink hover:bg-vellum transition-colors"
            >
              {s.identifier}
              <span className="text-xs text-trace ml-2">{s.item_type}</span>
            </button>
          ))}
          {query.trim() && !exactMatch && !showTypeSelector && (
            <button
              type="button"
              onClick={() => setShowTypeSelector(true)}
              className="w-full text-left px-3 py-2 text-sm text-ink hover:bg-vellum transition-colors border-t border-rule"
            >
              Create "{query.trim()}"
            </button>
          )}
          {query.trim() && !exactMatch && showTypeSelector && (
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
