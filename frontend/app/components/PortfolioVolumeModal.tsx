'use client';

import { useEffect, useState } from 'react';
import { X, TrendingUp } from 'lucide-react';
import axios from 'axios';
import { VolumeHistory } from '../types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface PortfolioVolumeModalProps {
  ticker: string;
  currentVolume: number;
  onClose: () => void;
}

export default function PortfolioVolumeModal({ ticker, currentVolume, onClose }: PortfolioVolumeModalProps) {
  const [volumeHistory, setVolumeHistory] = useState<VolumeHistory[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchVolumeHistory = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/volume-history/${ticker}`);
        setVolumeHistory(response.data);
      } catch (error) {
        console.error('Error fetching volume history:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchVolumeHistory();
  }, [ticker]);

  const avgVolume = volumeHistory.length > 0
    ? volumeHistory.reduce((sum, v) => sum + v.volume, 0) / volumeHistory.length
    : 0;

  return (
    <div 
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80"
      onClick={onClose}
    >
      <div 
        className="bg-gray-950 border border-cyan-500/50 rounded-lg p-6 shadow-2xl w-[90vw] max-w-[600px] max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-cyan-400 flex items-center gap-2">
            <TrendingUp className="w-5 h-5" />
            {ticker} - 20-Day Volume History
          </h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {loading ? (
          <div className="text-center text-gray-400 py-8">Loading...</div>
        ) : (
          <>
            <div className="bg-gray-900 rounded p-4 mb-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-500">Current Volume</div>
                  <div className="text-white font-bold text-lg">{currentVolume.toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-gray-500">20-Day Average</div>
                  <div className="text-cyan-400 font-bold text-lg">{Math.round(avgVolume).toLocaleString()}</div>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="text-sm font-bold text-gray-400 mb-2">Daily Volume Breakdown (Most Recent First):</h4>
              <div className="max-h-[300px] overflow-y-auto space-y-1">
                {volumeHistory.slice().reverse().map((item, index) => (
                  <div 
                    key={index}
                    className="flex justify-between items-center bg-gray-900/50 p-2 rounded text-xs"
                  >
                    <span className="text-gray-400">{item.date}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-mono">{item.volume.toLocaleString()}</span>
                      <div 
                        className="w-24 h-2 bg-gray-800 rounded overflow-hidden"
                        title={`${((item.volume / avgVolume) * 100).toFixed(0)}% of average`}
                      >
                        <div 
                          className={`h-full ${
                            item.volume > avgVolume * 1.5 ? 'bg-green-500' : 
                            item.volume > avgVolume ? 'bg-yellow-500' : 
                            'bg-gray-600'
                          }`}
                          style={{ width: `${Math.min((item.volume / (avgVolume * 2)) * 100, 100)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-4 text-xs text-gray-500 bg-gray-900/30 p-3 rounded">
              <div className="font-bold text-gray-400 mb-1">Volume Indicators:</div>
              <div className="space-y-1">
                <div>🟢 Green: Above 1.5x average (High activity)</div>
                <div>🟡 Yellow: Above average (Moderate activity)</div>
                <div>⚫ Gray: Below average (Low activity)</div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
