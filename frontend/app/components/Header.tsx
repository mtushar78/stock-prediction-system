import { TrendingUp, RefreshCw } from 'lucide-react';
import { SystemStatus } from '../types';

interface HeaderProps {
  systemStatus: SystemStatus | null;
  loading: boolean;
  onRefresh: () => void;
}

export default function Header({ systemStatus, loading, onRefresh }: HeaderProps) {
  return (
    <header className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-700 pb-4 gap-4">
      <div>
        <h1 className="text-3xl font-bold text-green-400 flex items-center gap-2">
          <TrendingUp className="w-8 h-8" /> DSE SNIPER
        </h1>
        <p className="text-gray-500 text-sm">Algorithmic Volume Analysis Terminal</p>
      </div>
      <div className="flex gap-4 flex-wrap">
        <div className="bg-gray-800 px-4 py-2 rounded">
          <span className="text-gray-400 text-xs block">SYSTEM STATUS</span>
          <span className={`font-bold ${systemStatus?.status === 'ONLINE' ? 'text-green-500' : 'text-red-500'}`}>
            ● {systemStatus?.status || 'LOADING'}
          </span>
        </div>
        <div className="bg-gray-800 px-4 py-2 rounded">
          <span className="text-gray-400 text-xs block">MARKET</span>
          <span className={`font-bold ${systemStatus?.market_status === 'OPEN' ? 'text-green-500' : 'text-yellow-500'}`}>
            {systemStatus?.market_status || 'UNKNOWN'}
          </span>
        </div>
        <button 
          onClick={onRefresh}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-4 py-2 rounded flex items-center gap-2 transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>
    </header>
  );
}
