'use client';

import Link from 'next/link';
import { TrendingUp, RefreshCw, Activity, LogOut } from 'lucide-react';
import { SystemStatus } from '../types';
import { useAuth } from './AuthProvider';

interface HeaderProps {
  systemStatus: SystemStatus | null;
  loading: boolean;
  onRefresh: () => void;
}

export default function Header({ systemStatus, loading, onRefresh }: HeaderProps) {
  const { user, logout } = useAuth();
  return (
    <header className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-700 pb-4 gap-4">
      <div>
        <h1 className="text-3xl font-bold text-green-400 flex items-center gap-2">
          <TrendingUp className="w-8 h-8" /> DSE SNIPER
        </h1>
        <p className="text-gray-500 text-sm">Algorithmic Volume Analysis Terminal</p>
      </div>
      <div className="flex gap-2 flex-wrap items-center">
        <nav className="flex gap-1 text-sm">
          <Link
            href="/"
            className="px-3 py-1.5 rounded bg-emerald-700 text-white border border-emerald-600 flex items-center gap-1.5"
          >
            <TrendingUp className="w-4 h-4" /> Dashboard
          </Link>
          <Link
            href="/chart-analysis"
            className="px-3 py-1.5 rounded bg-gray-800 text-gray-300 border border-gray-700 hover:bg-purple-900/40 hover:text-purple-200 transition flex items-center gap-1.5"
          >
            <Activity className="w-4 h-4" /> Chart Analyst
          </Link>
          <Link
            href="/analyze"
            className="px-3 py-1.5 rounded bg-gray-800 text-gray-300 border border-gray-700 hover:bg-gray-700 hover:text-white transition"
          >
            Manual Analyze
          </Link>
        </nav>
        <div className="bg-gray-800 px-3 py-1.5 rounded border border-gray-700">
          <span className="text-gray-400 text-[10px] block">SYSTEM</span>
          <span className={`font-bold text-sm ${systemStatus?.status === 'ONLINE' ? 'text-green-500' : 'text-red-500'}`}>
            ● {systemStatus?.status || 'LOADING'}
          </span>
        </div>
        <div className="bg-gray-800 px-3 py-1.5 rounded border border-gray-700">
          <span className="text-gray-400 text-[10px] block">MARKET</span>
          <span className={`font-bold text-sm ${systemStatus?.market_status === 'OPEN' ? 'text-green-500' : 'text-yellow-500'}`}>
            {systemStatus?.market_status || 'UNKNOWN'}
          </span>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-3 py-1.5 rounded flex items-center gap-2 transition text-sm"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
        {user && (
          <div className="flex items-center gap-2 bg-gray-800 px-3 py-1.5 rounded border border-gray-700">
            <span className="text-gray-300 text-xs hidden sm:inline" title={user.email}>
              {user.email}
            </span>
            <button
              onClick={logout}
              title="Sign out"
              className="text-red-400 hover:text-red-300 flex items-center gap-1 text-sm"
            >
              <LogOut className="w-4 h-4" /> Logout
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
