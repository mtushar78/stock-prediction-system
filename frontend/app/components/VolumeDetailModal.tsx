'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import { Signal, VolumeHistory } from '../types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface VolumeDetailModalProps {
  signal: Signal;
  onClose: () => void;
}

export default function VolumeDetailModal({ signal, onClose }: VolumeDetailModalProps) {
  const [volumeHistory, setVolumeHistory] = useState<VolumeHistory[]>([]);
  const [loading, setLoading] = useState(true);
  
  const avgVolume = signal.AvgVolume20 || 0;
  const todayVolume = signal.Volume || 0;

  useEffect(() => {
    const fetchVolumeHistory = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/volume-history/${signal.Ticker}`);
        setVolumeHistory(response.data);
      } catch (error) {
        console.error('Error fetching volume history:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchVolumeHistory();
  }, [signal.Ticker]);

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80" onClick={onClose}>
      <div 
        className="bg-gray-950 border border-cyan-500/50 rounded-lg p-6 shadow-2xl w-[90vw] max-w-[700px] max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-xs font-mono">
          <div className="text-cyan-400 font-bold mb-3 text-sm border-b border-gray-700 pb-2">
            📊 VOLUME ANALYSIS - {signal.Ticker}
          </div>
          
          {/* Todays Volume */}
          <div className="mb-4">
            <div className="text-yellow-400 font-bold mb-2">📈 TODAY&apos;S VOLUME:</div>
            <div className="bg-gray-900 p-3 rounded">
              <div className="text-2xl text-white font-bold">{todayVolume.toLocaleString()}</div>
              <div className="text-gray-400 text-xs mt-1">shares traded</div>
            </div>
          </div>

          {/* RVOL Calculation */}
          <div className="mb-4 border-t border-gray-800 pt-3">
            <div className="text-purple-400 font-bold mb-2">🧮 RVOL CALCULATION:</div>
            <div className="bg-gray-900 p-3 rounded space-y-2">
              <div className="text-gray-300">
                <span className="text-cyan-400 font-bold">Formula:</span> RVOL = Today&apos;s Volume / 20-Day Average Volume
              </div>
              <div className="border-t border-gray-700 pt-2 mt-2">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <div className="text-gray-500">Today&apos;s Volume:</div>
                    <div className="text-white font-bold">{todayVolume.toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">20-Day Avg:</div>
                    <div className="text-white font-bold">{avgVolume.toLocaleString()}</div>
                  </div>
                </div>
              </div>
              <div className="border-t border-gray-700 pt-2 mt-2">
                <div className="text-gray-400">Calculation:</div>
                <div className="text-white font-mono">
                  {todayVolume.toLocaleString()} ÷ {avgVolume.toLocaleString()} = <span className="text-yellow-400 font-bold">{signal.RVOL}x</span>
                </div>
              </div>
              <div className={`mt-2 p-2 rounded ${signal.RVOL > 2.5 ? 'bg-green-900/30 text-green-400' : 'bg-gray-800 text-gray-400'}`}>
                {signal.RVOL > 2.5 ? '✅ Unusual Volume Detected!' : '⚠️ Normal Volume'}
              </div>
            </div>
          </div>

          {/* Last 20 Days */}
          <div className="border-t border-gray-800 pt-3">
            <div className="text-blue-400 font-bold mb-2">📅 LAST 20 DAYS VOLUME HISTORY:</div>
            {loading ? (
              <div className="text-center text-gray-400 py-8">Loading volume history...</div>
            ) : volumeHistory.length === 0 ? (
              <div className="text-center text-gray-400 py-8">No volume history available</div>
            ) : (
              <>
                <div className="bg-gray-900 p-3 rounded max-h-[300px] overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-gray-900">
                      <tr className="text-gray-500 border-b border-gray-700">
                        <th className="pb-2 text-left">Date</th>
                        <th className="pb-2 text-right">Volume</th>
                        <th className="pb-2 text-right">vs Avg</th>
                      </tr>
                    </thead>
                    <tbody>
                      {volumeHistory.slice().reverse().map((day, i) => {
                        const vsAvg = avgVolume > 0 ? ((day.volume / avgVolume) * 100 - 100).toFixed(1) : '0.0';
                        return (
                          <tr key={i} className="border-b border-gray-800">
                            <td className="py-2 text-gray-400">{day.date}</td>
                            <td className="py-2 text-right text-white">{day.volume.toLocaleString()}</td>
                            <td className={`py-2 text-right text-xs ${parseFloat(vsAvg) > 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {parseFloat(vsAvg) > 0 ? '+' : ''}{vsAvg}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="mt-2 text-gray-500 text-xs">
                  * Average Volume: {avgVolume.toLocaleString()} shares
                </div>
              </>
            )}
          </div>

          {/* Close Button */}
          <div className="mt-4 pt-3 border-t border-gray-800">
            <button
              onClick={onClose}
              className="w-full bg-cyan-600 hover:bg-cyan-700 text-white font-bold py-2 rounded transition"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
