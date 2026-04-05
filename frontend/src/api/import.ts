import { apiPostFormData, apiPost } from "./client";

// ─── Types ───────────────────────────────────────

export interface ImportMappingConfig {
  file_type: string;
  identifier_column: string;
  target_item_type: string;
  header_row: number;
  property_mapping: Record<string, string>;
  normalizations: Record<string, string>;
}

export interface ColumnProposal {
  column_name: string;
  proposed_property: string | null;
  confidence: number;
  match_method: string;
  alternatives: string[];
}

export interface ProposedMappingResponse {
  proposal_id: string;
  header_row: number;
  target_item_type: string;
  identifier_column: string;
  columns: ColumnProposal[];
  unmatched_columns: string[];
  proposed_config: ImportMappingConfig | null;
  overall_confidence: number;
  needs_user_review: boolean;
}

export interface MappingConfirmResponse {
  confirmed_config: ImportMappingConfig;
  corrections_saved: number;
  message: string;
}

export interface ImportSummary {
  items_imported: number;
  items_created: number;
  snapshots_created: number;
  source_changes: number;
  new_conflicts: number;
  resolved_conflicts: number;
  directives_fulfilled: number;
}

export interface ImportResult {
  batch_id: string;
  source_item_id: string;
  time_context_id: string;
  summary: ImportSummary;
}

// ─── API calls ───────────────────────────────────

export async function analyzeFile(
  file: File,
  sourceItemId?: string,
  projectId?: string,
): Promise<ProposedMappingResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (sourceItemId) formData.append("source_item_id", sourceItemId);
  if (projectId) formData.append("project_id", projectId);
  return apiPostFormData<ProposedMappingResponse>("/v1/import/analyze", formData);
}

export async function confirmMapping(
  proposalId: string,
  corrections: Record<string, string | null>,
  targetTypeOverride?: string,
): Promise<MappingConfirmResponse> {
  return apiPost<MappingConfirmResponse>(
    `/v1/import/analyze/${proposalId}/confirm`,
    {
      corrections,
      ...(targetTypeOverride ? { target_item_type: targetTypeOverride } : {}),
    },
  );
}

export async function runImport(
  file: File,
  sourceItemId: string,
  timeContextId: string,
  mappingConfig?: ImportMappingConfig,
): Promise<ImportResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("source_item_id", sourceItemId);
  formData.append("time_context_id", timeContextId);
  if (mappingConfig) {
    formData.append("mapping_config", JSON.stringify(mappingConfig));
  }
  return apiPostFormData<ImportResult>("/v1/import", formData);
}
