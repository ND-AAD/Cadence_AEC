// ─── Item Notes ──────────────────────────────────────────────────
// Notes section at the bottom of item views.
// Displays a list of notes for the current item with a "+ Add Note" button.
// When expanded, shows a textarea for composing new notes.
//
// Anatomy:
//   ─ divider line
//   △  Note content...
//      Author · YYYY-MM-DD
//   [+ Add Note]

import { useState, useCallback } from "react";
import { useNotes } from "@/hooks/useNotes";

interface ItemNotesProps {
  /** The item to show/add notes for. */
  itemId: string;
  /** Author name for new notes. */
  userName?: string;
}

export function ItemNotes({ itemId, userName = "" }: ItemNotesProps) {
  const { notes, addNote } = useNotes(itemId);
  const [isExpanded, setIsExpanded] = useState(false);
  const [draft, setDraft] = useState("");

  const handleAdd = useCallback(async () => {
    if (!draft.trim()) return;
    try {
      await addNote(draft.trim(), userName);
      setDraft("");
      setIsExpanded(false);
    } catch (err) {
      console.error("Failed to add note:", err);
    }
  }, [draft, addNote, userName]);

  return (
    <div className="border-t border-rule">
      {/* Notes list (newest first) */}
      {notes.length > 0 && (
        <div className="px-3 py-3 space-y-2">
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
                  <p className="font-sans text-xs leading-[18px] text-ink">
                    {note.content}
                  </p>
                  {(note.author || note.created_at) && (
                    <p className="font-mono text-[11px] text-trace mt-0.5">
                      {[
                        note.author,
                        note.created_at
                          ? new Date(note.created_at).toLocaleDateString()
                          : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add note button / form */}
      {!isExpanded ? (
        <div className="px-3 py-3 flex justify-center">
          <button
            type="button"
            onClick={() => setIsExpanded(true)}
            className="text-xs text-trace hover:text-graphite transition-colors duration-100"
          >
            + Add Note
          </button>
        </div>
      ) : (
        <div className="px-3 py-3 space-y-1.5">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="w-full font-sans text-xs border border-rule rounded px-2 py-1.5 bg-transparent resize-y min-h-[48px] focus:outline-none focus:border-graphite"
            placeholder="Add a note…"
            autoFocus
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setDraft("");
                setIsExpanded(false);
              }}
              className="bg-transparent text-graphite text-xs px-2 py-0.5 hover:text-ink transition-colors duration-100"
            >
              Cancel
            </button>
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
    </div>
  );
}
