'use client';

import { useState, useEffect } from 'react';
import axios from 'axios';
import { Wallet, PlusCircle, Clock, Info, AlertCircle } from 'lucide-react';
import Header from './components/Header';
import AlertsSection from './components/AlertsSection';
import VolumeDetailModal from './components/VolumeDetailModal';
import { Signal, PortfolioItem, Alert, SystemStatus } from './types';

// API Base URL - Read from environment variable or fallback to localhost
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function Dashboard() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioItem[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Trade Form State
  const [newTicker, setNewTicker] = useState('');
  const [newPrice, setNewPrice] = useState('');
  const [newQty, setNewQty] = useState('');
  const [submitting, setSubmitting] = useState(false);
  
  // Modal State
  const [activeModal, setActiveModal] = useState<number | null>(null);
  const [volumeModalSignal, setVolumeModalSignal] = useState<Signal | null>(null);

  // Click outside handler (on backdrop)
  useEffect(() => {
    const handleEscKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setActiveModal(null);
      }
    };

    document.addEventListener('keydown', handleEscKey);
    return () => document.removeEventListener('keydown', handleEscKey);
  }, []);

  // Fetch Data
  const fetchData = async () => {
    try {
      setLoading(true);
      
      const [statusRes, sigRes, portRes, alertRes] = await Promise.all([
        axios.get(`${API_URL}/`),
        axios.get(`${API_URL}/api/sniper-signals`),
        axios.get(`${API_URL}/api/portfolio`),
        axios.get(`${API_URL}/api/alerts`)
      ]);
      
      setSystemStatus(statusRes.data);
      setSignals(sigRes.data);
      setPortfolio(portRes.data);
      setAlerts(alertRes.data);
      
    } catch (err) {
      console.error("API Error", err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch data on component mount
  useEffect(() => {
    fetchData();
    
    // Auto-refresh every 60 seconds
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, []);

  // Handle New Trade
  const handleAddTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!newTicker || !newPrice || !newQty) {
      alert("Please fill all fields");
      return;
    }
    
    setSubmitting(true);
    
    try {
      await axios.post(`${API_URL}/api/trade`, {
        ticker: newTicker,
        buy_price: parseFloat(newPrice),
        quantity: parseInt(newQty)
      });
      
      alert(`✅ ${newTicker} added to portfolio!`);
      
      // Clear form
      setNewTicker('');
      setNewPrice('');
      setNewQty('');
      
      // Refresh data
      fetchData();
      
    } catch (err: any) {
      alert(`❌ Error: ${err.response?.data?.detail || err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  // Handle Remove Position
  const handleRemovePosition = async (ticker: string) => {
    if (!confirm(`Remove ${ticker} from portfolio?`)) return;
    
    try {
      await axios.delete(`${API_URL}/api/trade/${ticker}`);
      alert(`✅ ${ticker} removed from portfolio`);
      fetchData();
    } catch (err: any) {
      alert(`❌ Error: ${err.response?.data?.detail || err.message}`);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-4 md:p-8 font-mono">
      <Header systemStatus={systemStatus} loading={loading} onRefresh={fetchData} />

      {/* Last Update Info */}
      {systemStatus && (
        <div className="mb-6 bg-gray-800/50 border border-gray-700 rounded p-3 flex flex-wrap gap-4 text-sm">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" />
            <span className="text-gray-400">Last Update:</span>
            <span className="text-gray-200">{systemStatus.last_update || 'N/A'}</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" />
            <span className="text-gray-400">Next Update:</span>
            <span className="text-blue-400">{systemStatus.next_update || '11 AM / 1 PM / 2:45 PM'}</span>
          </div>
        </div>
      )}

      <AlertsSection alerts={alerts} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* 🔭 SNIPER SIGNALS (LEFT COL) */}
        <div className="lg:col-span-2 space-y-6">
          <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h2 className="text-xl font-bold mb-4 text-green-300">🔭 Sniper Scope (Buy Signals)</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs border-b border-gray-700">
                    <th className="pb-3 pr-4">TICKER</th>
                    <th className="pb-3 pr-4">PRICE</th>
                    <th className="pb-3 pr-4">VOLUME</th>
                    <th className="pb-3 pr-4">RVOL</th>
                    <th className="pb-3 pr-4">SCORE</th>
                    <th className="pb-3">REASON</th>
                  </tr>
                </thead>
                <tbody>
                  {signals.map((sig, i) => (
                    <tr key={i} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition">
                      <td className="py-3 pr-4 font-bold text-green-400">{sig.Ticker}</td>
                      <td className="py-3 pr-4">{sig.Price}</td>
                      <td className="py-3 pr-4">
                        <button onClick={() => setVolumeModalSignal(sig)} className="flex items-center gap-1 hover:text-cyan-400 transition">
                          <span className="text-white">{(sig.Volume || 0).toLocaleString()}</span>
                          <AlertCircle className="w-3.5 h-3.5 text-cyan-400" />
                        </button>
                      </td>
                      <td className="py-3 pr-4 font-bold text-yellow-400">{sig.RVOL}x</td>
                      <td className="py-3 pr-4">
                        <span className={`px-2 py-1 rounded text-xs font-bold ${
                          sig.Score >= 80 ? 'bg-green-900 text-green-300' : 
                          sig.Score >= 45 ? 'bg-yellow-900 text-yellow-300' : 
                          'bg-gray-700 text-gray-300'
                        }`}>
                          {sig.Score}
                        </span>
                      </td>
                      <td className="py-3 text-xs text-gray-400 relative">
                        <div className="flex items-center gap-2">
                          <span>{sig.Reason}</span>
                          <button
                            onClick={() => setActiveModal(i)}
                            className="inline-flex items-center justify-center w-4 h-4 rounded-full hover:bg-gray-700 transition-colors"
                          >
                            <Info className={`w-3.5 h-3.5 transition-colors ${activeModal === i ? 'text-green-400' : 'text-gray-500'}`} />
                          </button>
                        </div>
                        
                        {/* Buy Signal Modal */}
                        {activeModal === i && (
                          <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80" onClick={() => setActiveModal(null)}>
                            <div 
                              className="bg-gray-950 border border-green-500/50 rounded-lg p-6 shadow-2xl w-[90vw] max-w-[600px] max-h-[90vh] overflow-y-auto"
                              onClick={(e) => e.stopPropagation()}
                            >
                            <div className="text-xs font-mono whitespace-pre-wrap select-text">
                              <div className="text-green-400 font-bold mb-3 text-sm border-b border-gray-700 pb-2">
                                📊 DETAILED CALCULATION BREAKDOWN
                              </div>
                              
                              <div className="mb-3">
                                <div className="text-yellow-400 font-bold">🎯 TICKER: {sig.Ticker}</div>
                                <div className="text-gray-300">Signal: <span className="text-green-400">{sig.Signal}</span> | Final Score: <span className="text-yellow-300">{sig.Score}/100</span></div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3 mb-3">
                                <div className="text-blue-400 font-bold mb-2">📈 RVOL (Relative Volume) CALCULATION:</div>
                                <div className="text-gray-400 mb-2">Formula: <span className="text-white">RVOL = Today's Volume / 20-Day Avg Volume</span></div>
                                <div className="bg-gray-900 p-2 rounded mb-2">
                                  <div>Today's Volume: <span className="text-white">{sig.Volume?.toLocaleString() || 'N/A'}</span></div>
                                  <div>20-Day Avg Vol: <span className="text-white">{sig.AvgVolume20?.toLocaleString() || 'N/A'}</span></div>
                                  <div>RVOL Result: <span className="text-yellow-300 font-bold">{sig.RVOL}x</span></div>
                                </div>
                                <div className={sig.RVOL > 2.5 ? 'text-green-400' : 'text-red-400'}>
                                  {sig.RVOL > 2.5 ? '✅ RVOL > 2.5 (Unusual volume activity detected!)' : '❌ RVOL ≤ 2.5 (Normal volume)'}
                                </div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3 mb-3 bg-gradient-to-r from-purple-900/20 to-transparent p-3 rounded">
                                <div className="text-purple-400 font-bold mb-2">🚀 v3 UPGRADE: PROJECTED RVOL (Intraday Accuracy)</div>
                                <div className="text-gray-400 mb-2 text-xs">
                                  Problem Solved: Previously, 11 AM snapshot showed falsely low RVOL (only 1 hour of volume vs full-day average)
                                </div>
                                <div className="bg-gray-900 p-2 rounded mb-2">
                                  <div className="text-cyan-300 font-bold mb-1">NEW LOGIC:</div>
                                  <div className="text-xs text-gray-300 space-y-1">
                                    <div>1️⃣ 20-Day Avg uses SHIFTED data (excludes today's partial)</div>
                                    <div>2️⃣ If intraday snapshot (is_final=0):</div>
                                    <div className="ml-4">• Calculate minutes elapsed since 10 AM</div>
                                    <div className="ml-4">• Project: (current_vol / minutes) × 270</div>
                                    <div className="ml-4">• Use projected volume for RVOL</div>
                                    <div>3️⃣ Example: 50k vol at 11 AM → projects to 650k by 2:30 PM</div>
                                  </div>
                                </div>
                                <div className="text-green-400 text-xs">
                                  ✅ Result: Catch breakouts at 11 AM instead of waiting for 2:45 PM close!
                                </div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3 mb-3">
                                <div className="text-purple-400 font-bold mb-2">🎲 SCORE CALCULATION (0-100 Points):</div>
                                <div className="bg-gray-900 p-2 rounded space-y-1">
                                  <div>Base Score: <span className="text-white">0</span></div>
                                  {sig.RVOL > 2.5 && <div className="text-green-400">+ 50 pts → RVOL &gt; 2.5 threshold</div>}
                                  {sig.RVOL > 2.5 && Math.abs(sig.PriceChange || 0) < 2 && <div className="text-green-400">+ 20 pts → Quiet Accumulation (Price Change &lt; 2%)</div>}
                                  {sig.Price > (sig.SMA200 || 0) ? 
                                    <div className="text-green-400">+ 10 pts → Price above 200-day SMA</div> : 
                                    <div className="text-red-400">- 50 pts → Price below 200-day SMA</div>
                                  }
                                  <div className="border-t border-gray-700 mt-2 pt-2">
                                    <div>Price: <span className="text-white">{sig.Price} BDT</span></div>
                                    <div>200-Day SMA: <span className="text-white">{sig.SMA200?.toFixed(2) || 'N/A'} BDT</span></div>
                                    <div>Price Change: <span className="text-white">{sig.PriceChange?.toFixed(2) || 'N/A'}%</span></div>
                                  </div>
                                  <div className="text-yellow-300 font-bold mt-2">Final Score: {sig.Score}/100</div>
                                </div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3 mb-3">
                                <div className="text-orange-400 font-bold mb-2">💡 SCORING RULES:</div>
                                <div className="space-y-1 text-gray-300">
                                  <div>✅ Score ≥ 80: <span className="text-green-400">Strong BUY</span> (High confidence)</div>
                                  <div>⚠️  Score 45-79: <span className="text-yellow-400">WAIT</span> (Monitor closely)</div>
                                  <div>❌ Score &lt; 45: <span className="text-red-400">PASS</span> (Not recommended)</div>
                                </div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3 mb-3">
                                <div className="text-cyan-400 font-bold mb-2">🔍 REASONS:</div>
                                <div className="text-gray-300 bg-gray-900 p-2 rounded">{sig.Reason}</div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3">
                                <div className="text-pink-400 font-bold mb-2">📚 ALGORITHM INFO:</div>
                                <div className="space-y-1 text-gray-400 text-xs">
                                  <div>• RVOL &gt; 2.5 = Unusual volume (potential syndicate activity)</div>
                                  <div>• Quiet Accumulation = High volume + Low price change</div>
                                  <div>• Low Float = Paid-up capital &lt; 50 Crores</div>
                                  <div>• SMA = Simple Moving Average (200 days)</div>
                                </div>
                              </div>
                            </div>
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                  {signals.length === 0 && (
                    <tr><td colSpan={5} className="py-6 text-center text-gray-600">
                      {loading ? 'Loading signals...' : 'No signals today. Market is sleeping.'}
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {/* 💼 PORTFOLIO TABLE */}
          <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h2 className="text-xl font-bold mb-4 text-blue-300 flex items-center gap-2">
              <Wallet className="w-6 h-6" /> Current Holdings
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs border-b border-gray-700">
                    <th className="pb-3 pr-4">TICKER</th>
                    <th className="pb-3 pr-4">AVG COST</th>
                    <th className="pb-3 pr-4">CURRENT</th>
                    <th className="pb-3 pr-4">QTY</th>
                    <th className="pb-3 pr-4">TOTAL COST</th>
                    <th className="pb-3 pr-4">MKT VALUE</th>
                    <th className="pb-3 pr-4">PROFIT</th>
                    <th className="pb-3 pr-4">STATUS</th>
                    <th className="pb-3">ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  {portfolio.map((item, i) => (
                    <tr key={i} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition">
                      <td className="py-3 pr-4 font-bold">{item.ticker}</td>
                      <td className="py-3 pr-4">{item.buy_price.toFixed(2)}</td>
                      <td className="py-3 pr-4">{item.current_price.toFixed(2)}</td>
                      <td className="py-3 pr-4">{item.quantity}</td>
                      <td className="py-3 pr-4">{(item.buy_price * item.quantity).toFixed(0)}</td>
                      <td className="py-3 pr-4 text-cyan-400">{(item.current_price * item.quantity).toFixed(0)}</td>
                      <td className="py-3 pr-4">
                        <span className={item.profit_pct >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {item.profit_pct >= 0 ? '+' : ''}{item.profit_pct.toFixed(2)}%
                        </span>
                        <div className="text-xs text-gray-500">
                          {item.profit_amount >= 0 ? '+' : ''}{item.profit_amount.toFixed(0)} BDT
                        </div>
                      </td>
                      <td className="py-3 pr-4 relative">
                        <div className="flex items-center gap-2">
                          <span className={`${
                            item.status === 'STOP_LOSS' ? 'text-red-500' :
                            item.status === 'TAKE_PROFIT' ? 'text-yellow-500' :
                            item.status === 'ZOMBIE_WARNING' ? 'text-orange-500' :
                            'text-green-500'
                          }`}>{item.status}</span>
                          <button
                            onClick={() => setActiveModal(signals.length + i)}
                            className="inline-flex items-center justify-center w-4 h-4 rounded-full hover:bg-gray-700 transition-colors"
                          >
                            <Info className={`w-3.5 h-3.5 transition-colors ${activeModal === signals.length + i ? 'text-blue-400' : 'text-gray-500'}`} />
                          </button>
                        </div>
                        
                        {/* Sell Logic Modal */}
                        {activeModal === signals.length + i && (
                          <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80" onClick={() => setActiveModal(null)}>
                            <div 
                              className="bg-gray-950 border border-blue-500/50 rounded-lg p-6 shadow-2xl w-[90vw] max-w-[650px] max-h-[90vh] overflow-y-auto"
                              onClick={(e) => e.stopPropagation()}
                            >
                            <div className="text-xs font-mono whitespace-pre-wrap select-text">
                              <div className="text-blue-400 font-bold mb-3 text-sm border-b border-gray-700 pb-2">
                                💰 LEVEL 2 SELL LOGIC - DETAILED BREAKDOWN
                              </div>
                              
                              <div className="mb-3">
                                <div className="text-yellow-400 font-bold">🎯 {item.ticker}</div>
                                <div className="text-gray-300">Status: <span className={`font-bold ${
                                  item.status === 'STOP_LOSS' ? 'text-red-500' :
                                  item.status === 'TAKE_PROFIT' ? 'text-yellow-500' :
                                  item.status === 'ZOMBIE_WARNING' ? 'text-orange-500' :
                                  'text-green-500'
                                }`}>{item.status}</span></div>
                                {item.is_zombie && <div className="text-orange-500 font-bold">🧟 ZOMBIE WARNING - Consider Exit</div>}
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3 mb-3">
                                <div className="text-blue-400 font-bold mb-2">📊 POSITION DETAILS:</div>
                                <div className="bg-gray-900 p-2 rounded space-y-1">
                                  <div>Buy Price: <span className="text-white">{item.buy_price.toFixed(2)} BDT</span></div>
                                  <div>Current Price: <span className="text-white">{item.current_price.toFixed(2)} BDT</span></div>
                                  <div>Highest Seen: <span className="text-yellow-300">{item.highest_seen.toFixed(2)} BDT</span></div>
                                  <div>Quantity: <span className="text-white">{item.quantity}</span></div>
                                  <div>Days Held: <span className={`font-bold ${item.days_held > 10 ? 'text-orange-400' : 'text-white'}`}>{item.days_held} days</span></div>
                                  <div>Profit: <span className={`font-bold ${item.profit_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {item.profit_pct >= 0 ? '+' : ''}{item.profit_pct.toFixed(2)}% ({item.profit_pct >= 0 ? '+' : ''}{item.profit_amount.toFixed(0)} BDT)
                                  </span></div>
                                </div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3 mb-3">
                                <div className="text-green-400 font-bold mb-2">🎯 ATR (Average True Range) - THE BREATHING ROOM:</div>
                                <div className="text-gray-400 mb-2">Theory: ATR measures stock's natural volatility over 14 days</div>
                                <div className="bg-gray-900 p-2 rounded mb-2">
                                  <div>ATR Value: <span className="text-yellow-300 font-bold">{item.atr.toFixed(2)} BDT</span></div>
                                  <div className="text-gray-400 text-xs mt-1">This stock typically moves ±{item.atr.toFixed(2)} BDT per day</div>
                                </div>
                                <div className="text-gray-300 text-xs space-y-1">
                                  <div>• Formula: TR = Max(High-Low, |High-PrevClose|, |Low-PrevClose|)</div>
                                  <div>• ATR = EMA of TR over 14 days</div>
                                  <div>• {item.atr < 2 ? '📍 Low volatility (stable stock)' : item.atr < 5 ? '📊 Medium volatility' : '🌊 High volatility (wild swings)'}</div>
                                </div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3 mb-3 bg-gradient-to-r from-purple-900/20 to-transparent p-3 rounded">
                                <div className="text-purple-400 font-bold mb-2">🚀 v3 UPGRADE: RSI-BASED DYNAMIC RATCHET</div>
                                <div className="text-gray-400 mb-2 text-xs">
                                  Problem Solved: Level 2 used fixed 2×ATR. Parabolic stocks crashed before stop hit.
                                </div>
                                <div className="bg-gray-900 p-2 rounded mb-2">
                                  <div className="text-cyan-300 font-bold mb-1">NEW LOGIC:</div>
                                  <div className="text-xs text-gray-300 space-y-1">
                                    <div>RSI (Relative Strength Index): <span className="text-yellow-300 font-bold">{item.rsi ? item.rsi.toFixed(1) : 'N/A'}</span></div>
                                    <div className="mt-2 border-t border-gray-700 pt-2">
                                      <div className="font-bold text-white">ATR MULTIPLIER LOGIC:</div>
                                      <div className="ml-2 mt-1 space-y-1">
                                        <div>• RSI &lt; 70: <span className="text-green-400">2.0× ATR</span> (Standard - let winners run)</div>
                                        <div>• RSI 70-80: <span className="text-yellow-400">1.5× ATR</span> (Tight - stock overheating)</div>
                                        <div>• RSI &gt; 80: <span className="text-red-400">1.0× ATR</span> (Aggressive - extreme parabolic)</div>
                                      </div>
                                    </div>
                                    <div className="mt-2 border-t border-gray-700 pt-2">
                                      <div className="font-bold text-white">Current Status:</div>
                                      <div className="ml-2">
                                        {item.rsi && item.rsi > 80 ? (
                                          <div className="text-red-400">🔴 RSI &gt; 80: Very tight stop (1.0× ATR) - Lock profits NOW!</div>
                                        ) : item.rsi && item.rsi > 70 ? (
                                          <div className="text-yellow-400">🟡 RSI &gt; 70: Tightening stop (1.5× ATR) - Watch closely</div>
                                        ) : (
                                          <div className="text-green-400">🟢 RSI &lt; 70: Loose stop (2.0× ATR) - Healthy trend</div>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                </div>
                                <div className="text-green-400 text-xs">
                                  ✅ Result: Protect profits at peak momentum while letting healthy uptrends run!
                                </div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3 mb-3">
                                <div className="text-purple-400 font-bold mb-2">🛡️ STOP LOSS LEVELS:</div>
                                <div className="bg-gray-900 p-2 rounded space-y-2">
                                  <div className="border-b border-gray-700 pb-2">
                                    <div className="text-red-400 font-bold">1️⃣ EMERGENCY BRAKE (-7%)</div>
                                    <div>Price: <span className="text-white">{item.stop_loss_price.toFixed(2)} BDT</span></div>
                                    <div className="text-xs text-gray-400">Hard stop at -7% from buy price</div>
                                    {item.current_price <= item.stop_loss_price && <div className="text-red-500 font-bold mt-1">⚠️ TRIGGERED! Sell immediately!</div>}
                                  </div>
                                  
                                  <div>
                                    <div className="text-yellow-400 font-bold">2️⃣ TRAILING STOP (v3: RSI-Adjusted ATR)</div>
                                    <div>Price: <span className="text-white">{item.trailing_stop_price.toFixed(2)} BDT</span></div>
                                    <div>Type: <span className="text-cyan-300">{item.stop_type}</span></div>
                                    {item.stop_type.includes('ATR') ? (
                                      <>
                                        <div className="text-xs text-gray-400 mt-1">
                                          Formula: Peak ({item.highest_seen.toFixed(2)}) - (Multiplier × ATR {item.atr.toFixed(2)}) = {item.trailing_stop_price.toFixed(2)}
                                        </div>
                                        <div className="text-xs text-green-400 mt-1">
                                          ✅ v3: Multiplier adjusts based on RSI momentum
                                        </div>
                                      </>
                                    ) : (
                                      <div className="text-xs text-gray-400 mt-1">
                                        Fallback: Fixed 5% from peak (ATR data unavailable)
                                      </div>
                                    )}
                                    {item.current_price <= item.trailing_stop_price && <div className="text-yellow-500 font-bold mt-1">⚠️ TRIGGERED! Trend broken, take profit!</div>}
                                  </div>
                                </div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3 mb-3">
                                <div className="text-orange-400 font-bold mb-2">🧟 ZOMBIE KILLER CHECK:</div>
                                <div className="text-gray-400 mb-2">Rule: IF Days Held &gt; 10 AND Profit &lt; 2% THEN SELL</div>
                                <div className="bg-gray-900 p-2 rounded">
                                  <div>Days Held: <span className={`font-bold ${item.days_held > 10 ? 'text-orange-400' : 'text-green-400'}`}>{item.days_held}</span> {item.days_held > 10 ? '> 10 ❌' : '≤ 10 ✅'}</div>
                                  <div>Profit: <span className={`font-bold ${item.profit_pct < 2 ? 'text-orange-400' : 'text-green-400'}`}>{item.profit_pct.toFixed(2)}%</span> {item.profit_pct < 2 ? '< 2% ❌' : '≥ 2% ✅'}</div>
                                  <div className="mt-2 border-t border-gray-700 pt-2">
                                    {item.is_zombie ? (
                                      <div className="text-orange-500 font-bold">🧟 ZOMBIE DETECTED! Free up capital for better trades</div>
                                    ) : (
                                      <div className="text-green-400">✅ Position is healthy (not a zombie)</div>
                                    )}
                                  </div>
                                </div>
                                <div className="text-gray-400 text-xs mt-2">
                                  Theory: Syndicates work fast. If no movement in 10 days, setup failed.
                                </div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3 mb-3">
                                <div className="text-cyan-400 font-bold mb-2">📈 VOLUME ANALYSIS:</div>
                                <div className="bg-gray-900 p-2 rounded">
                                  <div>Today's Volume: <span className="text-white">{item.volume?.toLocaleString() || 'N/A'}</span></div>
                                  <div>RVOL: <span className={`font-bold ${item.rvol > 2.5 ? 'text-yellow-400' : 'text-gray-400'}`}>{item.rvol.toFixed(2)}x</span></div>
                                  {item.rvol > 5 && item.profit_pct > 20 && (
                                    <div className="text-red-400 font-bold mt-2">⚠️ CLIMAX PATTERN: High RVOL + Profit &gt;20% - Watch for dump!</div>
                                  )}
                                </div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3 mb-3">
                                <div className="text-pink-400 font-bold mb-2">💡 LEVEL 1 VS LEVEL 2 COMPARISON:</div>
                                <div className="space-y-1 text-gray-300 text-xs">
                                  <div className="bg-gray-900 p-2 rounded">
                                    <div className="text-red-400 mb-1">❌ Level 1 (Old): Fixed 5% trailing stop</div>
                                    <div>Would be at: {(item.highest_seen * 0.95).toFixed(2)} BDT</div>
                                  </div>
                                  <div className="bg-gray-900 p-2 rounded mt-1">
                                    <div className="text-green-400 mb-1">✅ Level 2 (New): Dynamic 2×ATR trailing stop</div>
                                    <div>Currently at: {item.trailing_stop_price.toFixed(2)} BDT</div>
                                    <div className="mt-1">
                                      {item.stop_type === 'ATR' && (
                                        item.trailing_stop_price < (item.highest_seen * 0.95) ? 
                                        <span className="text-green-400">✅ Tighter stop (stable stock) - Better profit protection!</span> :
                                        <span className="text-green-400">✅ Looser stop (volatile stock) - More breathing room!</span>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </div>
                              
                              <div className="border-t border-gray-800 pt-3">
                                <div className="text-indigo-400 font-bold mb-2">📚 SELL SIGNAL PRIORITY:</div>
                                <div className="space-y-1 text-gray-300 text-xs">
                                  <div>1️⃣ <span className="text-red-500">STOP_LOSS</span> - Emergency Brake hit → SELL NOW</div>
                                  <div>2️⃣ <span className="text-yellow-500">TAKE_PROFIT</span> - ATR trailing stop hit → SELL NOW</div>
                                  <div>3️⃣ <span className="text-red-500">CLIMAX</span> - Volume spike at profit &gt;20% → SELL HALF</div>
                                  <div>4️⃣ <span className="text-orange-500">ZOMBIE_EXIT</span> - Dead position &gt;10 days → SELL</div>
                                  <div>5️⃣ <span className="text-green-500">HOLD</span> - All good, keep holding!</div>
                                </div>
                              </div>
                            </div>
                            </div>
                          </div>
                        )}
                      </td>
                      <td className="py-3">
                        <button 
                          onClick={() => handleRemovePosition(item.ticker)}
                          className="text-red-400 hover:text-red-300 text-xs underline"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                  {portfolio.length === 0 && (
                    <tr><td colSpan={7} className="py-6 text-center text-gray-600">
                      Portfolio is empty. Add your first trade →
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        {/* 📝 SIDEBAR (RIGHT COL) */}
        <div className="space-y-6">
          <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h2 className="text-xl font-bold mb-4 text-gray-100 flex items-center gap-2">
              <PlusCircle className="w-6 h-6" /> Record Trade
            </h2>
            <form onSubmit={handleAddTrade} className="space-y-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">TICKER SYMBOL</label>
                <input 
                  type="text" 
                  value={newTicker}
                  onChange={e => setNewTicker(e.target.value.toUpperCase())}
                  className="w-full bg-gray-900 border border-gray-600 rounded p-2 text-white focus:border-green-500 outline-none"
                  placeholder="e.g. ACI"
                  disabled={submitting}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">BUY PRICE</label>
                  <input 
                    type="number" 
                    step="0.01"
                    value={newPrice}
                    onChange={e => setNewPrice(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-600 rounded p-2 text-white focus:border-green-500 outline-none"
                    placeholder="0.00"
                    disabled={submitting}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">QTY</label>
                  <input 
                    type="number" 
                    value={newQty}
                    onChange={e => setNewQty(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-600 rounded p-2 text-white focus:border-green-500 outline-none"
                    placeholder="0"
                    disabled={submitting}
                  />
                </div>
              </div>
              <button 
                type="submit" 
                disabled={submitting}
                className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white font-bold py-3 rounded transition"
              >
                {submitting ? 'ADDING...' : 'ADD TO PORTFOLIO'}
              </button>
            </form>
          </section>

          <section className="bg-blue-900/20 rounded-lg p-6 border border-blue-800">
            <h3 className="text-sm font-bold text-blue-400 mb-2">ℹ️ SYSTEM INFO (v3)</h3>
            <div className="text-xs text-blue-200 space-y-2">
              <p>
                <strong>Auto-Update:</strong> 11:00 AM, 1:00 PM, 2:45 PM (Bangladesh Time)
              </p>
              <p>
                <strong>Data Source:</strong> Dhaka Stock Exchange via StockSurfer
              </p>
              <p>
                <strong>Analysis Engine:</strong> Projected RVOL + RSI-based trailing stops
              </p>
              <p>
                <strong>v3 Features:</strong> Intraday snapshots, dynamic ATR multiplier
              </p>
            </div>
          </section>

          {portfolio.length > 0 && (
            <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h3 className="text-sm font-bold text-gray-300 mb-3">📊 PORTFOLIO SUMMARY</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Positions:</span>
                  <span className="text-white font-bold">{portfolio.length}</span>
                </div>
                <div className="flex justify-between border-b border-gray-700 pb-2">
                  <span className="text-gray-500">Total Cost:</span>
                  <span className="text-white font-bold">
                    {portfolio.reduce((sum, p) => sum + (p.buy_price * p.quantity), 0).toFixed(0)} BDT
                  </span>
                </div>
                <div className="flex justify-between border-b border-gray-700 pb-2">
                  <span className="text-gray-500">Market Value:</span>
                  <span className="text-cyan-400 font-bold">
                    {portfolio.reduce((sum, p) => sum + (p.current_price * p.quantity), 0).toFixed(0)} BDT
                  </span>
                </div>
                <div className="flex justify-between pt-1">
                  <span className="text-gray-500 font-bold">Total P/L:</span>
                  <span className={`font-bold ${
                    portfolio.reduce((sum, p) => sum + p.profit_amount, 0) >= 0 
                      ? 'text-green-400' 
                      : 'text-red-400'
                  }`}>
                    {portfolio.reduce((sum, p) => sum + p.profit_amount, 0) >= 0 ? '+' : ''}
                    {portfolio.reduce((sum, p) => sum + p.profit_amount, 0).toFixed(0)} BDT
                  </span>
                </div>
              </div>
            </section>
          )}
        </div>

      </div>

      {/* Volume Detail Modal */}
      {volumeModalSignal && (
        <VolumeDetailModal 
          signal={volumeModalSignal} 
          onClose={() => setVolumeModalSignal(null)} 
        />
      )}
    </div>
  );
}
