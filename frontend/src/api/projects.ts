import { apiGet, apiPost } from "./client";

export interface ProjectItem {
  id: string;
  item_type: string;
  identifier: string;
  properties: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  items: ProjectItem[];
  total: number;
  limit: number;
  offset: number;
}

export async function listProjects(): Promise<ProjectListResponse> {
  return apiGet<ProjectListResponse>("/v1/items?item_type=project&limit=50");
}

export interface CreateProjectRequest {
  name: string;
  description?: string;
}

export async function createProject(req: CreateProjectRequest): Promise<ProjectItem> {
  return apiPost<ProjectItem>("/v1/items", {
    item_type: "project",
    identifier: req.name,
    properties: {
      description: req.description ?? "",
    },
  });
}
