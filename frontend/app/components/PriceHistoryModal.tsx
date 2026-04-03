'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import { PriceHistory } from '../types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface PriceHistoryModalProps {
  ticker: string;
  currentPrice?: number;
  onClose: () => void;
}

export default function PriceHistoryModal({ ticker, currentPrice, onClose }: PriceHistoryModalProps) {
  const [priceHistory, setPriceHistory] = useState<PriceHistory[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPriceHistory = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/price-history/${ticker}`);
        setPriceHistory(response.data);
      } catch (error) {
        console.error('Error fetching price history:', error);
      } finally {
        setLoading(false);
      }
    };

    setLoading(true);
    setPriceHistory([]);
    fetchPriceHistory();
  }, [ticker]);

  const lastClose = priceHistory.length ? priceHistory[priceHistory.length - 2]?.close : undefined;
  const changePct =
    currentPrice !== undefined && lastClose !== undefined && lastClose !== 0
      ? ((currentPrice - lastClose) / lastClose) * 100
      : null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80" onClick={onClose}>
      <div
        className="bg-gray-950 border border-emerald-500/50 rounded-lg p-6 shadow-2xl w-[90vw] max-w-[800px] max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-xs font-mono">
          <div className="text-emerald-400 font-bold mb-3 text-sm border-b border-gray-700 pb-2 flex items-center justify-between">
            <div>💹 PRICE HISTORY (OHLC) - {ticker}</div>
            <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-xl font-bold" aria-label="Close">
              ×
            </button>
          </div>

          {/* Summary */}
          <div className="mb-4 grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-gray-900 p-3 rounded">
              <div className="text-gray-400 text-xs">Current Price</div>
              <div className="text-white font-bold text-xl">{currentPrice !== undefined ? `৳${currentPrice}` : '-'}</div>
            </div>
            <div className="bg-gray-900 p-3 rounded">
              <div className="text-gray-400 text-xs">Last Close (from history)</div>
              <div className="text-white font-bold text-xl">{lastClose !== undefined ? `৳${lastClose}` : '-'}</div>
            </div>
            <div className="bg-gray-900 p-3 rounded">
              <div className="text-gray-400 text-xs">Change vs Last Close</div>
              <div className={`font-bold text-xl ${changePct === null ? 'text-gray-500' : changePct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {changePct === null ? '-' : `${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%`}
              </div>
            </div>
          </div>

          {/* Last 20 Days */}
          <div className="border-t border-gray-800 pt-3">
            <div className="text-blue-400 font-bold mb-2">📅 LAST 20 DAYS OHLC:</div>
            {loading ? (
              <div className="text-center text-gray-400 py-8">Loading price history...</div>
            ) : priceHistory.length === 0 ? (
              <div className="text-center text-gray-400 py-8">No price history available</div>
            ) : (
              <div className="bg-gray-900 p-3 rounded max-h-[380px] overflow-y-auto">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-gray-900">
                    <tr className="text-gray-500 border-b border-gray-700">
                      <th className="pb-2 text-left">Date</th>
                      <th className="pb-2 text-right">Open</th>
                      <th className="pb-2 text-right">High</th>
                      <th className="pb-2 text-right">Low</th>
                      <th className="pb-2 text-right">Close</th>
                      <th className="pb-2 text-right">Range</th>
                    </tr>
                  </thead>
                  <tbody>
                    {priceHistory
                      .slice()
                      .reverse()
                      .map((day, i) => {
                        const range = day.high !== null && day.low !== null ? day.high - day.low : null;
                        const isBull = day.close >= day.open;
                        return (
                          <tr key={i} className="border-b border-gray-800">
                            <td className="py-2 text-gray-400">{day.date}</td>
                            <td className="py-2 text-right text-white">{day.open?.toFixed?.(2) ?? day.open}</td>
                            <td className="py-2 text-right text-white">{day.high?.toFixed?.(2) ?? day.high}</td>
                            <td className="py-2 text-right text-white">{day.low?.toFixed?.(2) ?? day.low}</td>
                            <td className={`py-2 text-right font-bold ${isBull ? 'text-green-300' : 'text-red-300'}`}>
                              {day.close?.toFixed?.(2) ?? day.close}
                            </td>
                            <td className="py-2 text-right text-gray-300">{range === null ? '-' : range.toFixed(2)}</td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Close Button */}
          <div className="mt-4 pt-3 border-t border-gray-800">
            <button
              onClick={onClose}
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2 rounded transition"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
