import { apiPost, apiGet } from "./client";

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  name: string;
  password: string;
  invite_code: string;
}

export interface LoginResponse {
  token: string;
  user: { id: string; email: string; name: string };
}

export interface UserInfo {
  id: string;
  email: string;
  name: string;
}

export async function login(req: LoginRequest): Promise<LoginResponse> {
  return apiPost<LoginResponse>("/v1/auth/login", req);
}

export async function register(req: RegisterRequest): Promise<LoginResponse> {
  return apiPost<LoginResponse>("/v1/auth/register", req);
}

export async function getCurrentUser(): Promise<UserInfo> {
  return apiGet<UserInfo>("/v1/auth/me");
}
