import { useState, useEffect, useRef } from "react";
import { apiGet, apiPost } from "@/api/client";

interface MilestoneItem {
  id: string;
  identifier: string;
  properties: Record<string, unknown>;
}

interface ConnectedGroup {
  item_type: string;
  items: MilestoneItem[];
}

interface MilestoneComboboxProps {
  projectId: string;
  value: { id: string; name: string } | null;
  onChange: (val: { id: string; name: string } | null) => void;
}

function computeOrdinal(name: string, existingOrdinals: number[]): number {
  const upper = name.toUpperCase().replace(/[\s%]+/g, "");
  const match = upper.match(/^(\d+)?(SD|DD|CD|CA|BID)$/);
  if (match) {
    const percent = match[1] ? parseInt(match[1]) : 100;
    const phase = match[2];
    const phaseBase: Record<string, number> = {
      SD: 200, DD: 300, CD: 400, BID: 500, CA: 600,
    };
    const base = phaseBase[phase] ?? 100;
    return base - 100 + Math.round(percent);
  }
  const maxExisting = existingOrdinals.length > 0
    ? Math.max(...existingOrdinals)
    : 0;
  return maxExisting + 100;
}

export function MilestoneCombobox({ projectId, value, onChange }: MilestoneComboboxProps) {
  const [milestones, setMilestones] = useState<MilestoneItem[]>([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiGet<{ connected: ConnectedGroup[] }>(
          `/v1/items/${projectId}/connected`
        );
        const group = res.connected.find(
          (g) => g.item_type === "milestone" || g.item_type === "issuance"
        );
        if (group) {
          const sorted = [...group.items].sort((a, b) => {
            const aOrd = (a.properties?.ordinal as number) ?? 0;
            const bOrd = (b.properties?.ordinal as number) ?? 0;
            return aOrd - bOrd;
          });
          setMilestones(sorted);
        }
      } catch {
        // Silently fail — user can still type to create
      }
    })();
  }, [projectId]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = milestones.filter((m) =>
    m.identifier.toLowerCase().includes(query.toLowerCase())
  );

  const exactMatch = milestones.some(
    (m) => m.identifier.toLowerCase() === query.toLowerCase()
  );

  async function handleCreate() {
    if (!query.trim() || creating) return;
    setCreating(true);
    try {
      const existingOrdinals = milestones.map(
        (m) => (m.properties?.ordinal as number) ?? 0
      );
      const ordinal = computeOrdinal(query.trim(), existingOrdinals);

      const milestone = await apiPost<MilestoneItem>("/v1/items", {
        item_type: "milestone",
        identifier: query.trim(),
        properties: { ordinal },
      });

      // Connect to project
      await apiPost("/v1/connections", {
        source_item_id: projectId,
        target_item_id: milestone.id,
      });

      setMilestones((prev) => [...prev, milestone].sort((a, b) => {
        const aOrd = (a.properties?.ordinal as number) ?? 0;
        const bOrd = (b.properties?.ordinal as number) ?? 0;
        return aOrd - bOrd;
      }));

      onChange({ id: milestone.id, name: milestone.identifier });
      setQuery("");
      setOpen(false);
    } catch {
      // Show inline error if needed
    } finally {
      setCreating(false);
    }
  }

  function handleSelect(m: MilestoneItem) {
    onChange({ id: m.id, name: m.identifier });
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

      {open && (query || milestones.length > 0) && (
        <div className="absolute z-10 mt-1 w-full bg-sheet border border-rule shadow-sm max-h-48 overflow-auto">
          {filtered.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => handleSelect(m)}
              className="w-full text-left px-3 py-2 text-sm text-ink hover:bg-vellum transition-colors"
            >
              {m.identifier}
              <span className="text-xs text-trace ml-2">
                ord: {(m.properties?.ordinal as number) ?? "—"}
              </span>
            </button>
          ))}
          {query.trim() && !exactMatch && (
            <button
              type="button"
              onClick={handleCreate}
              disabled={creating}
              className="w-full text-left px-3 py-2 text-sm text-ink hover:bg-vellum transition-colors border-t border-rule"
            >
              {creating ? "Creating…" : `Create "${query.trim()}"`}
            </button>
          )}
          {filtered.length === 0 && !query.trim() && (
            <p className="px-3 py-2 text-xs text-trace">No milestones yet — type to create one</p>
          )}
        </div>
      )}
    </div>
  );
}
