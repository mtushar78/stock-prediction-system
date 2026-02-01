import { PortfolioItem } from '../types';

interface PortfolioSummaryProps {
  portfolio: PortfolioItem[];
}

export default function PortfolioSummary({ portfolio }: PortfolioSummaryProps) {
  const totalCost = portfolio.reduce((sum, p) => sum + (p.buy_price * p.quantity), 0);
  const totalValue = portfolio.reduce((sum, p) => sum + (p.current_price * p.quantity), 0);
  const totalPL = portfolio.reduce((sum, p) => sum + p.profit_amount, 0);

  return (
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
            {totalCost.toFixed(0)} BDT
          </span>
        </div>
        <div className="flex justify-between border-b border-gray-700 pb-2">
          <span className="text-gray-500">Market Value:</span>
          <span className="text-cyan-400 font-bold">
            {totalValue.toFixed(0)} BDT
          </span>
        </div>
        <div className="flex justify-between pt-1">
          <span className="text-gray-500 font-bold">Total P/L:</span>
          <span className={`font-bold ${totalPL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {totalPL >= 0 ? '+' : ''}{totalPL.toFixed(0)} BDT
          </span>
        </div>
      </div>
    </section>
  );
}
