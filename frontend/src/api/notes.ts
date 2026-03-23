// ─── Notes/Cairn API ─────────────────────────────────────────────
// CRUD for cairn items (human-authored notes connected to items).

import { apiGet, apiPost } from "./client";

export interface Note {
  id: string;
  content: string;
  author: string;
  item_id: string;
  created_at: string;
}

export interface NoteListResponse {
  notes: Note[];
}

/** List all notes for an item, newest first. */
export async function listNotes(itemId: string): Promise<NoteListResponse> {
  return apiGet<NoteListResponse>(`/v1/items/${itemId}/notes`);
}

/** Create a cairn (note) connected to the target item. */
export async function createNote(
  itemId: string,
  content: string,
  author: string,
): Promise<Note> {
  return apiPost<Note>(`/v1/items/${itemId}/notes`, { content, author });
}

/** Delete a note by its item ID. */
export async function deleteNote(noteId: string): Promise<void> {
  const response = await fetch(
    `${import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api` : "/api"}/v1/items/${noteId}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw new Error(`Failed to delete note: ${response.status}`);
  }
}
