// ─── Notes Area ──────────────────────────────────────────────────
// Bottom zone of the exec summary dock.
// DS-2 §10.7: Contextual notes for the currently viewed item.
//
// Distinct from the Notes tree category (global rollup).
// This tracks the main story panel's current item.
//
// Anatomy:
//   NOTES · n                    ▾
//   △  Note content...
//      Author · YYYY-MM-DD
//   [Add a note...              ]
//                         [Add]

import { useState, useCallback } from "react";

export interface NoteData {
  id: string;
  content: string;
  author?: string;
  date?: string;
}

interface NotesAreaProps {
  /** Notes for the current item (newest first). */
  notes: NoteData[];
  /** Whether the current item exists (to show empty state). */
  hasCurrentItem: boolean;
  /** Called when user adds a new note. */
  onAddNote?: (content: string) => void;
}

export function NotesArea({
  notes,
  hasCurrentItem,
  onAddNote,
}: NotesAreaProps) {
  const [collapsed, setCollapsed] = useState(notes.length === 0);
  const [draft, setDraft] = useState("");

  const handleAdd = useCallback(() => {
    if (!draft.trim() || !onAddNote) return;
    onAddNote(draft.trim());
    setDraft("");
  }, [draft, onAddNote]);

  return (
    <div className="border-t border-rule">
      {/* Header */}
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-board/20 transition-colors duration-100"
      >
        <span className="text-xs font-mono uppercase text-trace tracking-wider">
          Notes · {notes.length}
        </span>
        <span className="text-xs text-trace">
          {collapsed ? "▸" : "▾"}
        </span>
      </button>

      {/* Content */}
      {!collapsed && (
        <div className="px-3 pb-3">
          {!hasCurrentItem ? (
            <div className="text-xs text-trace py-2">
              Navigate to an item to see notes.
            </div>
          ) : (
            <>
              {/* Note list */}
              {notes.length > 0 ? (
                <div className="space-y-2 mb-3">
                  {notes.map((note) => (
                    <div key={note.id} className="border-b border-rule pb-2 last:border-b-0">
                      <div className="flex items-start gap-1.5">
                        {/* Cairn triangle */}
                        <svg
                          width="10"
                          height="10"
                          viewBox="0 0 10 10"
                          className="text-trace shrink-0 mt-0.5"
                        >
                          <path
                            d="M5 2L9.5 8.5H0.5L5 2Z"
                            fill="currentColor"
                          />
                        </svg>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-ink leading-[18px]">
                            {note.content}
                          </p>
                          {(note.author || note.date) && (
                            <p className="text-[11px] text-trace font-mono mt-0.5">
                              {[note.author, note.date].filter(Boolean).join(" · ")}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-trace py-1 mb-2">
                  No notes on this item.
                </div>
              )}

              {/* Add note input */}
              {onAddNote && (
                <div className="space-y-1.5">
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    rows={2}
                    className="w-full text-xs border border-rule rounded px-2 py-1.5 bg-transparent resize-y min-h-[48px] focus:outline-none focus:border-graphite"
                    placeholder="Add a note…"
                  />
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={handleAdd}
                      disabled={!draft.trim()}
                      className="bg-transparent text-graphite border border-rule-emphasis rounded text-xs px-2 py-0.5 hover:text-ink hover:border-graphite transition-colors duration-100 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Add
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
