/**
 * SmartHire AI — Auth helpers (client-side)
 * Thin wrappers around the API client for all auth operations.
 */

import { api, setTokens, clearTokens } from "@/lib/api";

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export async function login(payload: LoginPayload): Promise<User> {
  const tokens = await api.post<TokenResponse>("/auth/login", payload);
  setTokens(tokens.access_token, tokens.refresh_token);
  return api.get<User>("/auth/me");
}

export async function register(payload: RegisterPayload): Promise<User> {
  return api.post<User>("/auth/register", payload);
}

export async function logout(): Promise<void> {
  try {
    await api.post("/auth/logout");
  } finally {
    clearTokens();
  }
}

export async function getMe(): Promise<User> {
  return api.get<User>("/auth/me");
}

export function isAuthenticated(): boolean {
  if (typeof window === "undefined") return false;
  return !!localStorage.getItem("access_token");
}
