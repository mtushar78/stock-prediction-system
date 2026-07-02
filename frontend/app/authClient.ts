'use client';

import axios from 'axios';

// Base URL matches the pattern used across the app's components.
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const TOKEN_KEY = 'dse_token';
const USER_KEY = 'dse_user';

export interface AuthUser {
  id: number;
  email: string;
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

/**
 * Set (or clear) the global axios Authorization header. Because every
 * component in this app calls the default `axios` instance directly, setting
 * this once makes all existing API calls authenticated automatically.
 */
export function applyAuthHeader(token: string | null): void {
  if (token) {
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete axios.defaults.headers.common['Authorization'];
  }
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const res = await axios.post(`${API_URL}/api/auth/login`, { email, password });
  const { access_token, user } = res.data as { access_token: string; user: AuthUser };
  localStorage.setItem(TOKEN_KEY, access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  applyAuthHeader(access_token);
  return user;
}

export function logout(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  applyAuthHeader(null);
}
