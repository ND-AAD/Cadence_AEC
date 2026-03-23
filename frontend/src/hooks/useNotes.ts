// ─── useNotes Hook ───────────────────────────────────────────────
// Fetch, create, and delete cairn notes for the current item.
// Re-fetches when itemId changes. Provides optimistic-style refresh.

import { useState, useEffect, useCallback } from "react";
import { listNotes, createNote, deleteNote, type Note } from "@/api/notes";

export interface UseNotesResult {
  notes: Note[];
  loading: boolean;
  error: string | null;
  /** Create a note on the current item. Refreshes the list after. */
  addNote: (content: string, author: string) => Promise<void>;
  /** Delete a note by ID. Refreshes the list after. */
  removeNote: (noteId: string) => Promise<void>;
  /** Manually refresh the notes list. */
  refresh: () => void;
}

export function useNotes(itemId: string | null): UseNotesResult {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchNotes = useCallback(async () => {
    if (!itemId) {
      setNotes([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await listNotes(itemId);
      setNotes(data.notes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notes");
    } finally {
      setLoading(false);
    }
  }, [itemId]);

  useEffect(() => {
    fetchNotes();
  }, [fetchNotes]);

  const addNote = useCallback(
    async (content: string, author: string) => {
      if (!itemId) return;
      try {
        await createNote(itemId, content, author);
        await fetchNotes();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create note");
      }
    },
    [itemId, fetchNotes],
  );

  const removeNote = useCallback(
    async (noteId: string) => {
      try {
        await deleteNote(noteId);
        await fetchNotes();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete note");
      }
    },
    [fetchNotes],
  );

  return { notes, loading, error, addNote, removeNote, refresh: fetchNotes };
}
