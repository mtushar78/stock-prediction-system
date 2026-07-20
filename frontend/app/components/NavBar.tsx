'use client';

/**
 * NavBar — the ONE top navigation bar, shared by every authenticated page.
 *
 * Rendered once globally (see AuthProvider) so the menu is identical everywhere
 * and the active page is always highlighted. It owns its own system-status poll
 * so the data-freshness badge is consistent on every page; page-specific
 * controls (per-page Refresh, "as of" dates) stay in each page's own title row.
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import axios from 'axios';
import {
  TrendingUp,
  Activity,
  Rocket,
  Zap,
  Landmark,
  Radar,
  Calculator,
  Settings,
  LogOut,
  Sprout,
  BookOpen,
  type LucideIcon,
} from 'lucide-react';
import { SystemStatus } from '../types';
import { useAuth } from './AuthProvider';
import DataFreshnessBadge from './DataFreshnessBadge';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Tailwind classes for the active pill — static strings so JIT keeps them. */
  active: string;
}

const NAV: NavItem[] = [
  { href: '/', label: 'Dashboard', icon: TrendingUp, active: 'bg-emerald-600 text-white border-emerald-500' },
  { href: '/chart-analysis', label: 'Chart Analyst', icon: Activity, active: 'bg-purple-600 text-white border-purple-500' },
  { href: '/coils', label: 'Coiled Springs', icon: Sprout, active: 'bg-fuchsia-600 text-white border-fuchsia-500' },
  { href: '/rebounds', label: 'Rebounds', icon: Rocket, active: 'bg-teal-600 text-white border-teal-500' },
  { href: '/momentum', label: 'Momentum', icon: Zap, active: 'bg-indigo-600 text-white border-indigo-500' },
  { href: '/long-term', label: 'Long-Term', icon: Landmark, active: 'bg-emerald-700 text-white border-emerald-600' },
  { href: '/news', label: 'News & Rumors', icon: Radar, active: 'bg-amber-600 text-white border-amber-500' },
  { href: '/analyze', label: 'Manual Analyze', icon: Calculator, active: 'bg-blue-600 text-white border-blue-500' },
  { href: '/playbook', label: 'Playbook', icon: BookOpen, active: 'bg-sky-600 text-white border-sky-500' },
];

function isActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function NavBar() {
  const pathname = usePathname();
  const { user, isAdmin, logout } = useAuth();
  const [status, setStatus] = useState<SystemStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchStatus = async () => {
      try {
        const res = await axios.get<SystemStatus>(`${API_URL}/`);
        if (!cancelled) setStatus(res.data);
      } catch {
        /* non-fatal — badge just shows "—" */
      }
    };
    fetchStatus();
    const id = setInterval(fetchStatus, 60000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const online = status?.status === 'ONLINE';

  return (
    <nav className="bg-gray-950/95 backdrop-blur border-b border-gray-800">
      <div className="px-3 sm:px-4 lg:px-6 flex items-center gap-2 sm:gap-3 h-14">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-1.5 shrink-0 mr-1" title="DSE Sniper">
          <TrendingUp className="w-6 h-6 text-green-400" />
          <span className="font-bold text-green-400 tracking-tight hidden sm:inline">DSE SNIPER</span>
        </Link>

        {/* Primary navigation */}
        <div className="flex-1 flex items-center gap-1 overflow-x-auto no-scrollbar">
          {NAV.map((item) => {
            const activeNow = isActive(pathname, item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={activeNow ? 'page' : undefined}
                className={`px-3 py-1.5 rounded-md border text-sm whitespace-nowrap flex items-center gap-1.5 transition ${
                  activeNow
                    ? item.active
                    : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800'
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="hidden md:inline">{item.label}</span>
              </Link>
            );
          })}
        </div>

        {/* Right cluster: status, settings, account */}
        <div className="flex items-center gap-2 shrink-0">
          <span
            className="hidden lg:flex items-center gap-1 text-xs"
            title={`System ${status?.status ?? 'loading'}`}
          >
            <span className={`w-2 h-2 rounded-full ${online ? 'bg-green-500' : 'bg-red-500'}`} />
          </span>

          <div className="hidden md:block">
            <DataFreshnessBadge systemStatus={status} />
          </div>

          <Link
            href="/settings"
            aria-current={pathname === '/settings' ? 'page' : undefined}
            title={isAdmin ? 'Settings & user management' : 'Account settings'}
            className={`p-2 rounded-md border transition ${
              pathname === '/settings'
                ? 'bg-gray-700 text-white border-gray-600'
                : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800'
            }`}
          >
            <Settings className="w-4 h-4" />
          </Link>

          {user && (
            <div className="flex items-center gap-2 pl-2 ml-1 border-l border-gray-800">
              <span className="text-gray-400 text-xs hidden lg:inline max-w-[160px] truncate" title={user.email}>
                {user.email}
              </span>
              {isAdmin && (
                <span className="text-[9px] bg-amber-600 text-white px-1 py-0.5 rounded font-bold hidden sm:inline">
                  ADMIN
                </span>
              )}
              <button
                onClick={logout}
                title="Sign out"
                className="text-red-400 hover:text-red-300 flex items-center gap-1 text-sm"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
