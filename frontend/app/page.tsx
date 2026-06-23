'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import axios from 'axios';
import { Clock } from 'lucide-react';
import Header from './components/Header';
import AlertsSection from './components/AlertsSection';
import SignalsTable from './components/SignalsTable';
import DateReplayBar from './components/DateReplayBar';
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
import { Signal, PortfolioItem, Alert, SystemStatus, PurchaseHistory, EntryGuidance } from './types';

// API Base URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function Dashboard() {
  // Data state
  const [signals, setSignals] = useState<Signal[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioItem[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);

  // Historical replay ("time machine") state
  const [tradingDates, setTradingDates] = useState<string[]>([]);
  const [histDate, setHistDate] = useState<string | null>(null);   // null = live
  const [histLoading, setHistLoading] = useState(false);
  const [histError, setHistError] = useState<string | null>(null);
  const histDateRef = useRef<string | null>(null);
  useEffect(() => { histDateRef.current = histDate; }, [histDate]);

  // Trade Form State
  const [newTicker, setNewTicker] = useState('');
  const [newPrice, setNewPrice] = useState('');
  const [newQty, setNewQty] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [tickers, setTickers] = useState<string[]>([]);
  const [priceLoading, setPriceLoading] = useState(false);
  const [priceSource, setPriceSource] = useState<'auto' | 'manual' | null>(null);
  const [priceFetchError, setPriceFetchError] = useState<string | null>(null);
  const [entryGuidance, setEntryGuidance] = useState<EntryGuidance | null>(null);
  
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

  // Fetch live data. When in replay mode, skip the live signals fetch so it
  // doesn't overwrite the historical signals being viewed.
  const fetchData = async (includeSignals = true) => {
    try {
      setLoading(true);
      const [statusRes, portRes, alertRes] = await Promise.all([
        axios.get(`${API_URL}/`),
        axios.get(`${API_URL}/api/portfolio`),
        axios.get(`${API_URL}/api/alerts`),
      ]);
      setSystemStatus(statusRes.data);
      setPortfolio(portRes.data);
      setAlerts(alertRes.data);
      if (includeSignals && histDateRef.current === null) {
        const sigRes = await axios.get(`${API_URL}/api/sniper-signals`);
        setSignals(sigRes.data);
      }
    } catch (err) {
      console.error("API Error", err);
    } finally {
      setLoading(false);
    }
  };

  // Load a past day's signals (lookahead-free; cached server-side).
  const loadHistorical = async (date: string) => {
    setHistDate(date);
    setHistError(null);
    setHistLoading(true);
    try {
      const res = await axios.get(`${API_URL}/api/sniper-signals/by-date`, {
        params: { date }, timeout: 180000,
      });
      setSignals(res.data);
      // Warm the next day so stepping forward is instant.
      const i = tradingDates.indexOf(date);
      const newer = i > 0 ? tradingDates[i - 1] : null;
      if (newer) axios.get(`${API_URL}/api/sniper-signals/by-date`, { params: { date: newer }, timeout: 180000 }).catch(() => {});
    } catch (err: unknown) {
      const e = err as { response?: { status?: number; data?: { detail?: string } } };
      setHistError(e.response?.status === 404
        ? `${date} wasn't a trading day — use Prev/Next.`
        : `Couldn't load ${date}. Try again.`);
    } finally {
      setHistLoading(false);
    }
  };

  const goLive = () => {
    setHistDate(null);
    setHistError(null);
    histDateRef.current = null;
    fetchData(true);
  };

  // Load the trading-date list once (for the replay picker).
  useEffect(() => {
    axios.get<string[]>(`${API_URL}/api/trading-dates`)
      .then((res) => setTradingDates(res.data || []))
      .catch(() => { /* non-fatal */ });
  }, []);

  // Auto-fetch and refresh. In replay mode, refresh only live portfolio/alerts.
  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(histDateRef.current === null), 60000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Trade form error message (inline, not alert)
  const [tradeError, setTradeError] = useState<string | null>(null);

  // Load the full ticker list once for autocomplete
  useEffect(() => {
    let cancelled = false;
    axios.get<string[]>(`${API_URL}/api/tickers`)
      .then((res) => { if (!cancelled) setTickers(res.data || []); })
      .catch(() => { /* non-fatal */ });
    return () => { cancelled = true; };
  }, []);

  // Auto-fetch last close when ticker is set to a valid symbol.
  // Debounced 250 ms so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const ticker = newTicker.trim().toUpperCase();
    if (!ticker) { setPriceSource(null); setPriceFetchError(null); setEntryGuidance(null); return; }
    // Only auto-fetch if the symbol exists in the loaded list
    // (so typing partial chars doesn't fire requests).
    if (tickers.length > 0 && !tickers.includes(ticker)) return;
    // If user is in the middle of manually editing the price, don't overwrite
    if (priceSource === 'manual') return;

    let cancelled = false;
    const handle = setTimeout(() => {
      setPriceLoading(true);
      setPriceFetchError(null);
      axios.get<Array<{ close: number; date: string }>>(`${API_URL}/api/price-history/${ticker}`)
        .then((res) => {
          if (cancelled) return;
          // The endpoint returns oldest-first (last element = most recent close).
          const arr = res.data || [];
          const lastClose = arr.length > 0 ? arr[arr.length - 1].close : undefined;
          if (typeof lastClose === 'number' && lastClose > 0) {
            setNewPrice(String(lastClose));
            setPriceSource('auto');
          } else {
            setPriceFetchError('no recent close');
          }
        })
        .then(() =>
          axios.get<EntryGuidance>(`${API_URL}/api/entry-guidance/${ticker}`)
            .then((res) => { if (!cancelled) setEntryGuidance(res.data); })
            .catch(() => { if (!cancelled) setEntryGuidance(null); })
        )
        .catch(() => {
          if (!cancelled) setPriceFetchError('fetch failed');
        })
        .finally(() => { if (!cancelled) setPriceLoading(false); });
    }, 250);

    return () => { cancelled = true; clearTimeout(handle); };
    // priceSource intentionally excluded — we only re-fetch on ticker / list change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [newTicker, tickers]);

  // Handle New Trade
  const handleAddTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    setTradeError(null);

    const ticker = newTicker.trim().toUpperCase();
    const price = parseFloat(newPrice);
    const qty = parseInt(newQty, 10);

    if (!ticker) { setTradeError('Ticker is required.'); return; }
    if (Number.isNaN(price) || price <= 0) {
      setTradeError('Buy price must be a number greater than 0.'); return;
    }
    if (Number.isNaN(qty) || qty <= 0) {
      setTradeError('Quantity must be a positive whole number (not 0).'); return;
    }

    setSubmitting(true);
    try {
      await axios.post(`${API_URL}/api/trade`, {
        ticker, buy_price: price, quantity: qty,
      });
      setNewTicker(''); setNewPrice(''); setNewQty('');
      setPriceSource(null); setPriceFetchError(null);
      setTradeError(null);
      fetchData();
    } catch (err: unknown) {
      const e = err as {
        response?: { status?: number; data?: { detail?: unknown } };
        message?: string;
      };
      // FastAPI 422 returns detail as a list of validator errors — flatten cleanly
      let msg = '';
      const detail = e.response?.data?.detail;
      if (Array.isArray(detail)) {
        msg = detail.map((d: { msg?: string; loc?: unknown[] }) =>
          `${(d.loc || []).join('.')}: ${d.msg}`).join('; ');
      } else if (typeof detail === 'string') {
        msg = detail;
      } else {
        msg = e.message || 'Unknown error';
      }
      setTradeError(msg);
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
          <DateReplayBar
            dates={tradingDates}
            value={histDate}
            loading={histLoading}
            error={histError}
            onPick={loadHistorical}
            onLive={goLive}
          />
          <SignalsTable
            signals={signals}
            loading={loading || histLoading}
            onVolumeClick={(signal) => setVolumeModalSignal(signal)}
            onInfoClick={(signal) => setActiveModal(signals.indexOf(signal))}
            onPriceInfoClick={(signal) => setPriceHistoryModal({ ticker: signal.Ticker, currentPrice: signal.Price })}
            activeTicker={activeModal !== null && activeModal < signals.length ? signals[activeModal]?.Ticker ?? null : null}
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
            error={tradeError}
            tickers={tickers}
            priceLoading={priceLoading}
            priceSource={priceSource}
            priceFetchError={priceFetchError}
            guidance={entryGuidance}
            onTickerChange={(v) => {
              setNewTicker(v);
              // Clear any pending error and reset the price source so a fresh
              // auto-fetch can run when the user picks a new symbol.
              setTradeError(null);
              setPriceSource(null);
              setNewPrice('');
              setEntryGuidance(null);
            }}
            onPriceChange={(v) => {
              setNewPrice(v);
              setTradeError(null);
              setPriceSource('manual'); // user is overriding; don't auto-overwrite
            }}
            onQtyChange={(v) => { setNewQty(v); setTradeError(null); }}
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
