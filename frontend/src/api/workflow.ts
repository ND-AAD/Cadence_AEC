// ─── Workflow API ─────────────────────────────────────────────────
// Status transition endpoints for workflow items (Decision 13).
// Replaces FE-2's in-memory acknowledge pattern with real persistence.

import { apiPost } from "./client";

// ─── Response Types ──────────────────────────────────────────────

export interface StatusTransitionResponse {
  item_id: string;
  item_type: string;
  previous_status: string;
  new_status: string;
}

export interface AcknowledgeResponse {
  change_item_id: string;
  status: string;
}

// ─── API Functions ───────────────────────────────────────────────

/**
 * Acknowledge a detected change.
 * Transitions: detected → acknowledged.
 */
export async function acknowledgeChange(
  changeItemId: string,
): Promise<AcknowledgeResponse> {
  return apiPost<AcknowledgeResponse>(
    `/v1/items/${changeItemId}/acknowledge`,
    {},
  );
}

/**
 * Start review on a workflow item.
 * Transitions: detected → in_review.
 * DS-2 §6.3: Signals active examination.
 */
export async function startReview(
  itemId: string,
): Promise<StatusTransitionResponse> {
  return apiPost<StatusTransitionResponse>(
    `/v1/items/${itemId}/start-review`,
    {},
  );
}

/**
 * Place a workflow item on hold.
 * Transitions: detected|in_review|pending → hold.
 * DS-2 §6.5: Stores pre-hold status for resume.
 */
export async function holdItem(
  itemId: string,
): Promise<StatusTransitionResponse> {
  return apiPost<StatusTransitionResponse>(
    `/v1/items/${itemId}/hold`,
    {},
  );
}

/**
 * Resume a held workflow item.
 * Transitions: hold → (restored pre-hold status).
 * DS-2 §6.5: Restores detected or in_review.
 */
export async function resumeReview(
  itemId: string,
): Promise<StatusTransitionResponse> {
  return apiPost<StatusTransitionResponse>(
    `/v1/items/${itemId}/resume-review`,
    {},
  );
}
