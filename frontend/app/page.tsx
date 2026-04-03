'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import axios from 'axios';
import { Clock } from 'lucide-react';
import Header from './components/Header';
import AlertsSection from './components/AlertsSection';
import SignalsTable from './components/SignalsTable';
import PortfolioTable from './components/PortfolioTable';
import TradeForm from './components/TradeForm';
import SystemInfoBox from './components/SystemInfoBox';
import PortfolioSummary from './components/PortfolioSummary';
import VolumeDetailModal from './components/VolumeDetailModal';
import PortfolioVolumeModal from './components/PortfolioVolumeModal';
import SignalDetailModal from './components/SignalDetailModal';
import PortfolioDetailModal from './components/PortfolioDetailModal';
import PurchaseHistoryModal from './components/PurchaseHistoryModal';
import PriceHistoryModal from './components/PriceHistoryModal';
import { Signal, PortfolioItem, Alert, SystemStatus, PurchaseHistory } from './types';

// API Base URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function Dashboard() {
  // Data state
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
  const [portfolioVolumeModal, setPortfolioVolumeModal] = useState<{ ticker: string; volume: number } | null>(null);
  const [purchaseHistoryModal, setPurchaseHistoryModal] = useState<string | null>(null);
  const [purchaseHistory, setPurchaseHistory] = useState<PurchaseHistory[]>([]);

  const [priceHistoryModal, setPriceHistoryModal] = useState<{ ticker: string; currentPrice?: number } | null>(null);

  // Keyboard shortcut handler
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

  // Auto-fetch and refresh
  useEffect(() => {
    fetchData();
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
      setNewTicker('');
      setNewPrice('');
      setNewQty('');
      fetchData();
    } catch (err: unknown) {
      const maybeAxiosError = err as { response?: { data?: { detail?: string } }; message?: string };
      alert(`❌ Error: ${maybeAxiosError.response?.data?.detail || maybeAxiosError.message || 'Unknown error'}`);
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
    } catch (err: unknown) {
      const maybeAxiosError = err as { response?: { data?: { detail?: string } }; message?: string };
      alert(`❌ Error: ${maybeAxiosError.response?.data?.detail || maybeAxiosError.message || 'Unknown error'}`);
    }
  };

  // Handle Purchase History Click
  const handlePurchaseHistoryClick = async (ticker: string) => {
    try {
      const res = await axios.get(`${API_URL}/api/purchase-history/${ticker}`);
      setPurchaseHistory(res.data);
      setPurchaseHistoryModal(ticker);
    } catch (err) {
      console.error('Error fetching purchase history:', err);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-4 md:p-8 font-mono">
      <Header systemStatus={systemStatus} loading={loading} onRefresh={fetchData} />

      {/* Quick navigation */}
      <div className="mb-6 flex flex-wrap gap-3">
        <Link
          href="/analyze"
          className="bg-gray-800 hover:bg-gray-700 border border-gray-700 px-4 py-2 rounded text-sm transition"
        >
          🧮 Manual Analyze
        </Link>
      </div>

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
        {/* MAIN CONTENT (LEFT - 2 COLS) */}
        <div className="lg:col-span-2 space-y-6">
          <SignalsTable 
            signals={signals}
            loading={loading}
            onVolumeClick={(signal) => setVolumeModalSignal(signal)}
            onInfoClick={(index) => setActiveModal(index)}
            onPriceInfoClick={(signal) => setPriceHistoryModal({ ticker: signal.Ticker, currentPrice: signal.Price })}
            activeModalIndex={activeModal}
          />
          
          <PortfolioTable 
            portfolio={portfolio}
            onVolumeClick={(ticker, volume) => setPortfolioVolumeModal({ ticker, volume })}
            onHistoryClick={handlePurchaseHistoryClick}
            onInfoClick={(index) => setActiveModal(signals.length + index)}
            onPriceInfoClick={(ticker, currentPrice) => setPriceHistoryModal({ ticker, currentPrice })}
            onRemove={handleRemovePosition}
            activeModalIndex={activeModal !== null && activeModal >= signals.length ? activeModal - signals.length : null}
          />
        </div>

        {/* SIDEBAR (RIGHT - 1 COL) */}
        <div className="space-y-6">
          <TradeForm 
            ticker={newTicker}
            price={newPrice}
            qty={newQty}
            submitting={submitting}
            onTickerChange={setNewTicker}
            onPriceChange={setNewPrice}
            onQtyChange={setNewQty}
            onSubmit={handleAddTrade}
          />
          
          <SystemInfoBox />
          
          {portfolio.length > 0 && <PortfolioSummary portfolio={portfolio} />}
        </div>
      </div>

      {/* MODALS */}
      {volumeModalSignal && (
        <VolumeDetailModal 
          signal={volumeModalSignal} 
          onClose={() => setVolumeModalSignal(null)} 
        />
      )}

      {portfolioVolumeModal && (
        <PortfolioVolumeModal 
          ticker={portfolioVolumeModal.ticker}
          currentVolume={portfolioVolumeModal.volume}
          onClose={() => setPortfolioVolumeModal(null)} 
        />
      )}

      {activeModal !== null && activeModal < signals.length && (
        <SignalDetailModal 
          signal={signals[activeModal]}
          onClose={() => setActiveModal(null)}
        />
      )}

      {activeModal !== null && activeModal >= signals.length && portfolio[activeModal - signals.length] && (
        <PortfolioDetailModal 
          item={portfolio[activeModal - signals.length]}
          onClose={() => setActiveModal(null)}
        />
      )}

      {purchaseHistoryModal && (
        <PurchaseHistoryModal 
          ticker={purchaseHistoryModal}
          history={purchaseHistory}
          onClose={() => setPurchaseHistoryModal(null)}
        />
      )}

      {priceHistoryModal && (
        <PriceHistoryModal
          ticker={priceHistoryModal.ticker}
          currentPrice={priceHistoryModal.currentPrice}
          onClose={() => setPriceHistoryModal(null)}
        />
      )}
    </div>
  );
}
