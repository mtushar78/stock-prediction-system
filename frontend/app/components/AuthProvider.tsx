'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import axios from 'axios';
import { UserCog, LogOut } from 'lucide-react';
import {
  getToken,
  getStoredUser,
  applyAuthHeader,
  logout as clearAuth,
  isImpersonating as readImpersonating,
  getAdminUser,
  stopImpersonation,
  AuthUser,
} from '../authClient';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const USER_KEY = 'dse_user';

interface AuthContextValue {
  user: AuthUser | null;
  isAdmin: boolean;
  isImpersonating: boolean;
  adminUser: AuthUser | null;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  isAdmin: false,
  isImpersonating: false,
  adminUser: null,
  logout: () => {},
});

export const useAuth = () => useContext(AuthContext);

/**
 * Client-side auth gate. It:
 *  - restores the token into the axios default header on load,
 *  - refreshes the effective user (incl. is_admin + impersonation) from the API,
 *  - installs a 401 interceptor that logs out + redirects to /login,
 *  - blocks rendering of protected pages until a token is present,
 *  - renders a persistent banner while an admin is impersonating a user.
 */
export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [impersonating, setImpersonating] = useState(false);
  const [adminUser, setAdminUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  // One-time setup: header + 401 interceptor + refresh identity from the API.
  useEffect(() => {
    applyAuthHeader(getToken());
    setUser(getStoredUser());
    setImpersonating(readImpersonating());
    setAdminUser(getAdminUser());

    const interceptorId = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error?.response?.status === 401) {
          clearAuth();
          setUser(null);
          if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
            router.replace('/login');
          }
        }
        return Promise.reject(error);
      }
    );

    // Refresh the effective identity so an already-logged-in session picks up
    // is_admin / impersonation without needing to log in again.
    if (getToken()) {
      axios
        .get(`${API_URL}/api/auth/me`)
        .then((res) => {
          const me = res.data as AuthUser & { impersonator?: { email: string } | null };
          const fresh: AuthUser = { id: me.id, email: me.email, is_admin: me.is_admin };
          setUser(fresh);
          localStorage.setItem(USER_KEY, JSON.stringify(fresh));
        })
        .catch(() => {
          /* interceptor handles 401; other errors are non-fatal */
        });
    }

    setReady(true);
    return () => axios.interceptors.response.eject(interceptorId);
  }, [router]);

  // Route guard: redirect based on token + current path.
  useEffect(() => {
    if (!ready) return;
    const token = getToken();
    if (!token && pathname !== '/login') {
      router.replace('/login');
    } else if (token && pathname === '/login') {
      router.replace('/');
    }
  }, [ready, pathname, router]);

  const logout = () => {
    clearAuth();
    setUser(null);
    router.replace('/login');
  };

  const returnToAdmin = () => {
    stopImpersonation();
    // Full reload so every component re-reads the restored admin session.
    window.location.assign('/settings');
  };

  // Avoid a flash of protected content before the guard runs.
  if (!ready) return null;
  if (!getToken() && pathname !== '/login') return null;

  const isAdmin = !!user?.is_admin;

  return (
    <AuthContext.Provider
      value={{ user, isAdmin, isImpersonating: impersonating, adminUser, logout }}
    >
      {impersonating && pathname !== '/login' && (
        <div className="sticky top-0 z-[60] bg-amber-500 text-black text-sm font-medium px-4 py-2 flex items-center justify-center gap-3 flex-wrap">
          <UserCog className="w-4 h-4" />
          <span>
            Viewing as <b>{user?.email}</b>
            {adminUser && <> · impersonated by <b>{adminUser.email}</b></>}
          </span>
          <button
            onClick={returnToAdmin}
            className="inline-flex items-center gap-1 bg-black/80 hover:bg-black text-white rounded px-2 py-0.5 text-xs font-bold transition"
          >
            <LogOut className="w-3 h-3" /> Return to admin
          </button>
        </div>
      )}
      {children}
    </AuthContext.Provider>
  );
}
