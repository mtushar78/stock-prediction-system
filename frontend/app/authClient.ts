'use client';

import axios from 'axios';

// Base URL matches the pattern used across the app's components.
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const TOKEN_KEY = 'dse_token';
const USER_KEY = 'dse_user';
// While an admin impersonates another user, the admin's own session is parked
// under these keys so "Return to admin" can restore it without re-login.
const ADMIN_TOKEN_KEY = 'dse_admin_token';
const ADMIN_USER_KEY = 'dse_admin_user';

export interface AuthUser {
  id: number;
  email: string;
  is_admin?: boolean;
}

export interface AdminUser {
  id: number;
  email: string;
  is_admin: boolean;
  created_at: string | null;
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

function setSession(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  applyAuthHeader(token);
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const res = await axios.post(`${API_URL}/api/auth/login`, { email, password });
  const { access_token, user } = res.data as { access_token: string; user: AuthUser };
  setSession(access_token, user);
  return user;
}

export function logout(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(ADMIN_TOKEN_KEY);
  localStorage.removeItem(ADMIN_USER_KEY);
  applyAuthHeader(null);
}

// --------------------------------------------------------------------------
// Self-service
// --------------------------------------------------------------------------
export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await axios.post(`${API_URL}/api/auth/change-password`, {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

// --------------------------------------------------------------------------
// Admin
// --------------------------------------------------------------------------
export async function adminListUsers(): Promise<AdminUser[]> {
  const res = await axios.get(`${API_URL}/api/admin/users`);
  return (res.data?.users ?? []) as AdminUser[];
}

export async function adminCreateUser(
  email: string,
  password: string,
  isAdmin = false,
): Promise<AdminUser> {
  const res = await axios.post(`${API_URL}/api/admin/users`, {
    email,
    password,
    is_admin: isAdmin,
  });
  return res.data as AdminUser;
}

export async function adminResetPassword(userId: number, newPassword: string): Promise<void> {
  await axios.post(`${API_URL}/api/admin/users/${userId}/password`, {
    new_password: newPassword,
  });
}

// --------------------------------------------------------------------------
// Impersonation
// --------------------------------------------------------------------------
export function isImpersonating(): boolean {
  if (typeof window === 'undefined') return false;
  return !!localStorage.getItem(ADMIN_TOKEN_KEY);
}

export function getAdminUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(ADMIN_USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

/**
 * Start impersonating a user. Parks the current (admin) session, then swaps in
 * a token issued for the target user. Returns the impersonated user.
 */
export async function startImpersonation(userId: number): Promise<AuthUser> {
  const res = await axios.post(`${API_URL}/api/admin/impersonate/${userId}`);
  const { access_token, user } = res.data as { access_token: string; user: AuthUser };
  const adminToken = getToken();
  const adminUser = getStoredUser();
  if (adminToken && adminUser) {
    localStorage.setItem(ADMIN_TOKEN_KEY, adminToken);
    localStorage.setItem(ADMIN_USER_KEY, JSON.stringify(adminUser));
  }
  setSession(access_token, user);
  return user;
}

/** Restore the parked admin session. */
export function stopImpersonation(): void {
  const adminToken = localStorage.getItem(ADMIN_TOKEN_KEY);
  const adminUser = localStorage.getItem(ADMIN_USER_KEY);
  if (adminToken && adminUser) {
    localStorage.setItem(TOKEN_KEY, adminToken);
    localStorage.setItem(USER_KEY, adminUser);
    applyAuthHeader(adminToken);
  }
  localStorage.removeItem(ADMIN_TOKEN_KEY);
  localStorage.removeItem(ADMIN_USER_KEY);
}
