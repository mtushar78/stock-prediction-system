'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import axios from 'axios';
import {
  getToken,
  getStoredUser,
  applyAuthHeader,
  logout as clearAuth,
  AuthUser,
} from '../authClient';

interface AuthContextValue {
  user: AuthUser | null;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  logout: () => {},
});

export const useAuth = () => useContext(AuthContext);

/**
 * Client-side auth gate. It:
 *  - restores the token into the axios default header on load,
 *  - installs a 401 interceptor that logs out + redirects to /login,
 *  - blocks rendering of protected pages until a token is present.
 */
export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  // One-time setup: header + 401 interceptor.
  useEffect(() => {
    applyAuthHeader(getToken());
    setUser(getStoredUser());

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

  // Avoid a flash of protected content before the guard runs.
  if (!ready) return null;
  if (!getToken() && pathname !== '/login') return null;

  return (
    <AuthContext.Provider value={{ user, logout }}>{children}</AuthContext.Provider>
  );
}
