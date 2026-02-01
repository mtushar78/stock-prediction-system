export default function SystemInfoBox() {
  return (
    <section className="bg-blue-900/20 rounded-lg p-6 border border-blue-800">
      <h3 className="text-sm font-bold text-blue-400 mb-2">ℹ️ SYSTEM INFO (v4 🔥)</h3>
      <div className="text-xs text-blue-200 space-y-2">
        <p>
          <strong>Auto-Update:</strong> 11:00 AM, 1:00 PM, 2:45 PM (Bangladesh Time)
        </p>
        <p>
          <strong>Data Source:</strong> Dhaka Stock Exchange via StockSurfer
        </p>
        <p>
          <strong>v4 NEW:</strong> 200 SMA trend filter (60-70% fewer losing trades!)
        </p>
        <p>
          <strong>v4 Features:</strong> Support/Resistance levels, R:R ratios, ATR stops
        </p>
        <p className="text-green-400">
          <strong>✅ Only shows stocks in UPTREND now!</strong>
        </p>
      </div>
    </section>
  );
}
