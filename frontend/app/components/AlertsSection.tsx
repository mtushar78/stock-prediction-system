import { AlertTriangle } from 'lucide-react';
import { Alert } from '../types';

interface AlertsSectionProps {
  alerts: Alert[];
}

export default function AlertsSection({ alerts }: AlertsSectionProps) {
  if (alerts.length === 0) return null;

  return (
    <section className="mb-8 bg-red-900/20 border border-red-600 rounded-lg p-4 animate-pulse">
      <h2 className="text-red-500 font-bold flex items-center gap-2 mb-3 text-xl">
        <AlertTriangle className="w-6 h-6" /> URGENT ACTION REQUIRED
      </h2>
      {alerts.map((alert, idx) => (
        <div key={idx} className="flex flex-col md:flex-row justify-between items-start md:items-center bg-red-950/50 p-4 rounded mb-2 gap-3">
          <div className="flex-1">
            <span className="font-bold text-2xl block mb-1">{alert.ticker}</span>
            <span className="text-red-300 text-sm block">{alert.reason}</span>
            <span className="text-gray-400 text-xs">Buy: {alert.buy_price} | Current: {alert.current_price}</span>
          </div>
          <div className="flex flex-col items-end gap-2">
            <span className={`text-xl font-bold ${alert.profit_amount >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {alert.value} ({alert.profit_amount >= 0 ? '+' : ''}{alert.profit_amount.toFixed(0)} BDT)
            </span>
            <span className="bg-red-600 text-white px-4 py-2 rounded font-bold">
              {alert.action}
            </span>
          </div>
        </div>
      ))}
    </section>
  );
}
