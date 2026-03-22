// ─── Navigation API ───────────────────────────────────────────────
// POST /api/navigate — breadcrumb navigation with bounce-back.

import { apiPost } from "./client";
import type { NavigateRequest, NavigateResponse } from "@/types/navigation";

/**
 * Navigate to a target item given the current breadcrumb path.
 *
 * Returns the new breadcrumb (as UUIDs) and the action taken:
 * - `push`: target was appended (forward navigation)
 * - `bounce_back`: breadcrumb was trimmed to a common ancestor, then target appended
 * - `no_path`: no connection path found; breadcrumb unchanged
 */
export async function navigateToItem(
  breadcrumbIds: string[],
  targetId: string,
): Promise<NavigateResponse> {
  const request: NavigateRequest = {
    breadcrumb: breadcrumbIds,
    target: targetId,
  };
  return apiPost<NavigateResponse>("/v1/navigate", request);
}
