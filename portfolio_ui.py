"""
Portfolio UI - Web Interface for The Harvest Module
A simple Flask-based UI for portfolio management and sell signals
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from portfolio_manager import PortfolioManager
from db_manager import DatabaseManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dse-sniper-harvest-2026'


@app.route('/')
def index():
    """Main dashboard showing portfolio and sell signals"""
    from datetime import datetime
    
    # Create database connections per request to avoid threading issues
    pm = PortfolioManager()
    db = DatabaseManager()
    
    portfolio = pm.get_portfolio()
    summary = pm.get_portfolio_summary()
    
    # Get sell signals
    signals = pm.check_sell_signals(verbose=False)
    
    # Get available tickers for dropdown
    all_tickers = db.get_all_tickers()
    
    # Close connections
    db.close()
    
    return render_template('portfolio_dashboard.html',
                         portfolio=portfolio.to_dict('records') if not portfolio.empty else [],
                         summary=summary,
                         signals=signals,
                         all_tickers=all_tickers,
                         today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/add_position', methods=['POST'])
def add_position():
    """Add a new position to portfolio"""
    pm = PortfolioManager()
    
    ticker = request.form.get('ticker')
    price = float(request.form.get('price'))
    quantity = int(request.form.get('quantity'))
    date = request.form.get('date')
    notes = request.form.get('notes', '')
    
    success = pm.add_trade(ticker, price, quantity, date if date else None, notes)
    
    if success:
        return jsonify({'status': 'success', 'message': f'{ticker} added successfully!'})
    else:
        return jsonify({'status': 'error', 'message': f'Failed to add {ticker}. Position may already exist.'}), 400


@app.route('/remove_position/<ticker>', methods=['POST'])
def remove_position(ticker):
    """Remove a position from portfolio"""
    pm = PortfolioManager()
    pm.remove_position(ticker)
    return jsonify({'status': 'success', 'message': f'{ticker} removed successfully!'})


@app.route('/check_signals')
def check_signals():
    """Check for sell signals and return JSON"""
    pm = PortfolioManager()
    signals = pm.check_sell_signals(verbose=False)
    return jsonify(signals)


@app.route('/update_data', methods=['POST'])
def update_data():
    """Trigger data update (would call stocksurfer_fetcher)"""
    # This would ideally trigger an update process
    # For now, just return success
    return jsonify({'status': 'success', 'message': 'Data update initiated'})


def create_template():
    """Create the HTML template"""
    template_dir = Path(__file__).parent / 'templates'
    template_dir.mkdir(exist_ok=True)
    
    template_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DSE Sniper - Portfolio Guardian</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 30px;
            text-align: center;
        }
        
        .header h1 {
            color: #2c3e50;
            margin-bottom: 10px;
        }
        
        .header p {
            color: #7f8c8d;
        }
        
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .card h3 {
            color: #7f8c8d;
            font-size: 14px;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        
        .card .value {
            color: #2c3e50;
            font-size: 32px;
            font-weight: bold;
        }
        
        .card.profit .value {
            color: #27ae60;
        }
        
        .card.loss .value {
            color: #e74c3c;
        }
        
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }
        
        @media (max-width: 1200px) {
            .main-grid {
                grid-template-columns: 1fr;
            }
        }
        
        .section {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .section h2 {
            color: #2c3e50;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }
        
        .form-group {
            margin-bottom: 15px;
        }
        
        .form-group label {
            display: block;
            color: #2c3e50;
            font-weight: 600;
            margin-bottom: 5px;
        }
        
        .form-group input, .form-group select {
            width: 100%;
            padding: 12px;
            border: 2px solid #ecf0f1;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .btn:hover {
            transform: translateY(-2px);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            padding: 8px 15px;
            width: auto;
            font-size: 14px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        
        table th {
            background: #f8f9fa;
            padding: 15px;
            text-align: left;
            color: #2c3e50;
            font-weight: 600;
            border-bottom: 2px solid #ecf0f1;
        }
        
        table td {
            padding: 15px;
            border-bottom: 1px solid #ecf0f1;
            color: #2c3e50;
        }
        
        table tr:hover {
            background: #f8f9fa;
        }
        
        .alert {
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-weight: 600;
        }
        
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 2px solid #c3e6cb;
        }
        
        .alert-warning {
            background: #fff3cd;
            color: #856404;
            border: 2px solid #ffeeba;
        }
        
        .alert-danger {
            background: #f8d7da;
            color: #721c24;
            border: 2px solid #f5c6cb;
        }
        
        .signal-badge {
            display: inline-block;
            padding: 8px 15px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 12px;
        }
        
        .signal-hold {
            background: #d4edda;
            color: #155724;
        }
        
        .signal-sell {
            background: #f8d7da;
            color: #721c24;
        }
        
        .signal-sell-half {
            background: #fff3cd;
            color: #856404;
        }
        
        .profit-positive {
            color: #27ae60;
            font-weight: bold;
        }
        
        .profit-negative {
            color: #e74c3c;
            font-weight: bold;
        }
        
        .refresh-btn {
            background: #3498db;
            padding: 10px 20px;
            margin-bottom: 20px;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #95a5a6;
        }
        
        .empty-state i {
            font-size: 48px;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🎯 DSE Sniper - Portfolio Guardian</h1>
            <p>The Harvest Module: Discipline & Mathematics</p>
        </div>
        
        <!-- Summary Cards -->
        <div class="summary-cards">
            <div class="card">
                <h3>Total Positions</h3>
                <div class="value">{{ summary.total_positions }}</div>
            </div>
            <div class="card">
                <h3>Total Invested</h3>
                <div class="value">{{ "{:,.0f}".format(summary.total_invested) }} BDT</div>
            </div>
            <div class="card">
                <h3>Current Value</h3>
                <div class="value">{{ "{:,.0f}".format(summary.current_value) }} BDT</div>
            </div>
            <div class="card {% if summary.total_profit >= 0 %}profit{% else %}loss{% endif %}">
                <h3>Total Profit/Loss</h3>
                <div class="value">{{ "{:+,.0f}".format(summary.total_profit) }} BDT</div>
                <p style="margin-top: 5px; color: #7f8c8d;">{{ "{:+.2f}".format(summary.profit_pct) }}%</p>
            </div>
        </div>
        
        <!-- Sell Signals Alert -->
        {% if signals %}
        <div class="alert alert-danger">
            🚨 <strong>{{ signals|length }} SELL SIGNAL(S) DETECTED!</strong> Review your positions below.
        </div>
        {% endif %}
        
        <!-- Main Grid -->
        <div class="main-grid">
            <!-- Add Position Form -->
            <div class="section">
                <h2>➕ Add New Position</h2>
                <form id="addPositionForm">
                    <div class="form-group">
                        <label for="ticker">Stock Ticker *</label>
                        <select id="ticker" name="ticker" required>
                            <option value="">Select a stock...</option>
                            {% for ticker in all_tickers %}
                            <option value="{{ ticker }}">{{ ticker }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="price">Buy Price (BDT) *</label>
                        <input type="number" id="price" name="price" step="0.01" required placeholder="e.g., 21.50">
                    </div>
                    
                    <div class="form-group">
                        <label for="quantity">Quantity (Shares) *</label>
                        <input type="number" id="quantity" name="quantity" required placeholder="e.g., 500">
                    </div>
                    
                    <div class="form-group">
                        <label for="date">Purchase Date</label>
                        <input type="date" id="date" name="date" value="{{ today }}">
                    </div>
                    
                    <div class="form-group">
                        <label for="notes">Notes (Optional)</label>
                        <input type="text" id="notes" name="notes" placeholder="e.g., Buy signal from DSE Sniper">
                    </div>
                    
                    <button type="submit" class="btn">Add to Portfolio</button>
                </form>
            </div>
            
            <!-- Current Portfolio -->
            <div class="section">
                <h2>📊 Current Portfolio</h2>
                <button class="btn refresh-btn" onclick="location.reload()">🔄 Refresh Data</button>
                
                {% if portfolio %}
                <table>
                    <thead>
                        <tr>
                            <th>Ticker</th>
                            <th>Buy Price</th>
                            <th>Quantity</th>
                            <th>Highest</th>
                            <th>Date</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for position in portfolio %}
                        <tr>
                            <td><strong>{{ position.ticker }}</strong></td>
                            <td>{{ "{:.2f}".format(position.buy_price) }}</td>
                            <td>{{ position.quantity }}</td>
                            <td>{{ "{:.2f}".format(position.highest_seen) }}</td>
                            <td>{{ position.purchase_date }}</td>
                            <td>
                                <button class="btn btn-danger" onclick="removePosition('{{ position.ticker }}')">Remove</button>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <div class="empty-state">
                    <div style="font-size: 48px;">📭</div>
                    <p>No positions in portfolio</p>
                    <p style="margin-top: 10px; font-size: 14px;">Add your first position using the form on the left</p>
                </div>
                {% endif %}
            </div>
        </div>
        
        <!-- Sell Signals Section -->
        <div class="section">
            <h2>⚡ The Guardian's Verdict - Sell Signals</h2>
            
            {% if signals %}
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Action</th>
                        <th>Current</th>
                        <th>Buy Price</th>
                        <th>Profit</th>
                        <th>Reason</th>
                        <th>Urgency</th>
                    </tr>
                </thead>
                <tbody>
                    {% for signal in signals %}
                    <tr>
                        <td><strong>{{ signal.ticker }}</strong></td>
                        <td>
                            {% if 'SELL NOW' in signal.action %}
                            <span class="signal-badge signal-sell">{{ signal.action }}</span>
                            {% elif 'HALF' in signal.action %}
                            <span class="signal-badge signal-sell-half">{{ signal.action }}</span>
                            {% else %}
                            <span class="signal-badge signal-hold">{{ signal.action }}</span>
                            {% endif %}
                        </td>
                        <td>{{ "{:.2f}".format(signal.current_price) }}</td>
                        <td>{{ "{:.2f}".format(signal.buy_price) }}</td>
                        <td class="{% if signal.profit_pct >= 0 %}profit-positive{% else %}profit-negative{% endif %}">
                            {{ "{:+.2f}".format(signal.profit_pct) }}%<br>
                            <small>{{ "{:+,.0f}".format(signal.profit_amount) }} BDT</small>
                        </td>
                        <td>{{ signal.reason }}</td>
                        <td>
                            <strong style="color: {% if signal.urgency == 'CRITICAL' %}#e74c3c{% elif signal.urgency == 'HIGH' %}#f39c12{% else %}#3498db{% endif %}">
                                {{ signal.urgency }}
                            </strong>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% elif portfolio %}
            <div class="alert alert-success">
                ✅ All positions are safe. No sell signals detected.
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Status</th>
                        <th>Current</th>
                        <th>Buy Price</th>
                        <th>Highest</th>
                        <th>Profit</th>
                        <th>Stop Loss</th>
                        <th>Trail Stop</th>
                    </tr>
                </thead>
                <tbody>
                    {% for position in portfolio %}
                    <tr>
                        <td><strong>{{ position.ticker }}</strong></td>
                        <td><span class="signal-badge signal-hold">HOLD ✅</span></td>
                        <td>-</td>
                        <td>{{ "{:.2f}".format(position.buy_price) }}</td>
                        <td>{{ "{:.2f}".format(position.highest_seen) }}</td>
                        <td>-</td>
                        <td>{{ "{:.2f}".format(position.buy_price * 0.93) }}</td>
                        <td>{{ "{:.2f}".format(position.highest_seen * 0.95) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="empty-state">
                <div style="font-size: 48px;">✅</div>
                <p>No positions to monitor</p>
            </div>
            {% endif %}
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; color: white; margin-top: 30px; padding: 20px;">
            <p><strong>⚠️ Trading Discipline:</strong> When the system says SELL, you SELL. No excuses. No "wait one more day."</p>
            <p style="margin-top: 10px; opacity: 0.8;">Emergency Brake: -7% | The Ratchet: -5% from peak | The Climax: RVOL >5x</p>
        </div>
    </div>
    
    <script>
        // Add Position Form Handler
        document.getElementById('addPositionForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            
            try {
                const response = await fetch('/add_position', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    alert('✅ ' + result.message);
                    location.reload();
                } else {
                    alert('❌ ' + result.message);
                }
            } catch (error) {
                alert('❌ Error: ' + error.message);
            }
        });
        
        // Remove Position Handler
        async function removePosition(ticker) {
            if (!confirm(`Are you sure you want to remove ${ticker} from your portfolio?`)) {
                return;
            }
            
            try {
                const response = await fetch(`/remove_position/${ticker}`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                alert('✅ ' + result.message);
                location.reload();
            } catch (error) {
                alert('❌ Error: ' + error.message);
            }
        }
        
        // Auto-refresh every 5 minutes
        setTimeout(() => location.reload(), 300000);
    </script>
</body>
</html>'''
    
    template_file = template_dir / 'portfolio_dashboard.html'
    with open(template_file, 'w', encoding='utf-8') as f:
        f.write(template_html)
    
    print(f"Template created at: {template_file}")


if __name__ == '__main__':
    # Create template if it doesn't exist
    create_template()
    
    print("\n" + "="*60)
    print("🎯 DSE SNIPER - PORTFOLIO GUARDIAN UI")
    print("="*60)
    print("\nStarting web interface...")
    print("\n📍 Open your browser and go to: http://localhost:8080")
    print("\n⚠️  Press CTRL+C to stop the server")
    print("="*60 + "\n")
    
    app.run(debug=True, host='127.0.0.1', port=8080)
