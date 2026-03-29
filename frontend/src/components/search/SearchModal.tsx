// ─── Search Modal ─────────────────────────────────────────────────
// Global search overlay triggered by Cmd+K.
// DS-1 §8: Quick navigation to any item in the graph.
//
// Paper-and-ink aesthetic: border, no shadow, bg-sheet.
// Debounced search (300ms), arrow key navigation, Enter to select.

import { useState, useEffect, useRef, useCallback } from "react";
import { searchItems, type SearchResultItem } from "@/api/search";
import { itemDisplayName } from "@/utils/displayName";

interface SearchModalProps {
  projectId?: string;
  onNavigate: (itemId: string) => void;
  onClose: () => void;
}

export function SearchModal({ projectId, onNavigate, onClose }: SearchModalProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Autofocus on mount.
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Debounced search.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!query.trim()) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await searchItems(query.trim(), projectId);
        setResults(data.items);
        setSelectedIndex(0);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, projectId]);

  // Keyboard navigation.
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      switch (e.key) {
        case "Escape":
          e.preventDefault();
          onClose();
          break;
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
          break;
        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex((i) => Math.max(i - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          if (results[selectedIndex]) {
            onNavigate(results[selectedIndex].id);
          }
          break;
      }
    },
    [results, selectedIndex, onNavigate, onClose],
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-ink/20" />

      {/* Modal */}
      <div
        className="relative w-full max-w-md bg-sheet border border-rule rounded-md overflow-hidden animate-fade-in"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search input */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-rule">
          {/* Search icon */}
          <svg className="w-4 h-4 text-trace shrink-0" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M11 11l3.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search items…"
            className="flex-1 bg-transparent text-sm text-ink placeholder:text-trace outline-none font-mono"
          />
          <kbd className="text-xs text-trace border border-rule rounded px-1.5 py-0.5 font-mono">
            esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[320px] overflow-y-auto">
          {loading && (
            <div className="px-4 py-3 text-xs text-trace animate-pulse">
              Searching…
            </div>
          )}

          {!loading && query.trim() && results.length === 0 && (
            <div className="px-4 py-3 text-xs text-trace">
              No results found.
            </div>
          )}

          {!loading &&
            results.map((item, i) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavigate(item.id)}
                className={`w-full text-left px-4 py-2 flex items-center gap-3 text-sm transition-colors duration-75 ${
                  i === selectedIndex
                    ? "bg-board/60"
                    : "hover:bg-board/40"
                }`}
              >
                {/* Type badge */}
                <span className="text-xs font-mono text-trace px-1.5 py-0.5 rounded bg-vellum border border-rule shrink-0">
                  {item.item_type}
                </span>
                {/* Identifier */}
                <span className="font-mono text-ink truncate">
                  {itemDisplayName(item.identifier, item.item_type)}
                </span>
              </button>
            ))}
        </div>

        {/* Footer hint */}
        {!query.trim() && (
          <div className="px-4 py-2.5 text-xs text-trace border-t border-rule">
            Type to search items, properties, and sources.
          </div>
        )}
      </div>
    </div>
  );
}
