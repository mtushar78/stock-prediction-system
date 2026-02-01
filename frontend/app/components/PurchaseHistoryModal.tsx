import { History } from 'lucide-react';
import { PurchaseHistory } from '../types';

interface PurchaseHistoryModalProps {
  ticker: string;
  history: PurchaseHistory[];
  onClose: () => void;
}

export default function PurchaseHistoryModal({ ticker, history, onClose }: PurchaseHistoryModalProps) {
  return (
    <div 
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80"
      onClick={onClose}
    >
      <div 
        className="bg-gray-950 border border-purple-500/50 rounded-lg p-6 shadow-2xl w-[90vw] max-w-[700px] max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-purple-400 flex items-center gap-2">
            <History className="w-5 h-5" />
            {ticker} - Purchase History
          </h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 transition-colors text-xl font-bold"
          >
            ×
          </button>
        </div>

        {history.length === 0 ? (
          <div className="text-center text-gray-400 py-8">No purchase history found</div>
        ) : (
          <>
            <div className="bg-gray-900 rounded p-4 mb-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-500">Total Purchases</div>
                  <div className="text-white font-bold text-lg">{history.length}</div>
                </div>
                <div>
                  <div className="text-gray-500">Total Commission Paid</div>
                  <div className="text-orange-400 font-bold text-lg">
                    {history.reduce((sum, p) => sum + p.commission, 0).toFixed(2)} BDT
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="text-sm font-bold text-gray-400 mb-2">Purchase Breakdown:</h4>
              <div className="max-h-[400px] overflow-y-auto space-y-2">
                {history.map((item, index) => (
                  <div 
                    key={index}
                    className="bg-gray-900/50 p-3 rounded border border-gray-800"
                  >
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="text-gray-500">Date:</span>
                        <span className="text-white ml-2">{item.purchase_date}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Price:</span>
                        <span className="text-cyan-400 ml-2 font-bold">{item.buy_price.toFixed(2)} BDT</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Quantity:</span>
                        <span className="text-white ml-2 font-bold">{item.quantity}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Trade Value:</span>
                        <span className="text-white ml-2">{(item.buy_price * item.quantity).toFixed(2)} BDT</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Commission (0.40%):</span>
                        <span className="text-orange-400 ml-2 font-bold">{item.commission.toFixed(2)} BDT</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Total Cost:</span>
                        <span className="text-yellow-400 ml-2 font-bold">{item.total_cost.toFixed(2)} BDT</span>
                      </div>
                    </div>
                    {item.notes && (
                      <div className="mt-2 text-xs text-gray-500 italic border-t border-gray-800 pt-2">
                        Note: {item.notes}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-4 text-xs text-gray-500 bg-gray-900/30 p-3 rounded">
              <div className="font-bold text-gray-400 mb-1">💡 Commission Info:</div>
              <div>Every transaction includes a 0.40% stockhouse commission fee automatically calculated and added to your average cost.</div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
