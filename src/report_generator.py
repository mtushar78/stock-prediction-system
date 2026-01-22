"""
Report Generator for DSE Sniper System
Creates formatted reports from analysis results
"""

import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates formatted reports from analysis results"""
    
    def __init__(self, output_dir: str = "outputs/signals"):
        """
        Initialize report generator
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_console_report(self, df_results: pd.DataFrame, top_n: int = 20):
        """
        Generate and print console report
        
        Args:
            df_results: DataFrame with analysis results
            top_n: Number of top stocks to display
        """
        if df_results.empty:
            print("\n" + "="*80)
            print("NO SIGNALS GENERATED")
            print("="*80)
            return
        
        print("\n" + "="*80)
        print(f"DSE SNIPER - TRADING SIGNALS REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Summary statistics
        total_analyzed = len(df_results)
        buy_signals = len(df_results[df_results['signal'] == 'BUY'])
        wait_signals = len(df_results[df_results['signal'] == 'WAIT'])
        ignore_signals = len(df_results[df_results['signal'] == 'IGNORE'])
        
        print(f"\nSUMMARY:")
        print(f"  Total Analyzed: {total_analyzed}")
        print(f"  BUY Signals: {buy_signals}")
        print(f"  WAIT Signals: {wait_signals}")
        print(f"  IGNORE Signals: {ignore_signals}")
        
        # Top BUY signals
        buy_df = df_results[df_results['signal'] == 'BUY'].head(top_n)
        
        if not buy_df.empty:
            print(f"\n{'='*80}")
            print(f"TOP {len(buy_df)} BUY SIGNALS")
            print(f"{'='*80}")
            
            for idx, row in buy_df.iterrows():
                print(f"\n{idx+1}. {row['ticker']} - Score: {row['score']}")
                print(f"   Price: {row['close']} BDT | RVOL: {row['rvol']}x | Volume: {row['volume']:,}")
                print(f"   Change: {row['price_change_pct']:.2f}% | Avg Vol (20d): {row['avg_volume_20']:,}")
                
                if row['paid_up_capital']:
                    print(f"   Paid-Up Capital: {row['paid_up_capital']:.1f} Cr")
                
                if row['sma_200']:
                    sma_diff = ((row['close'] - row['sma_200']) / row['sma_200'] * 100)
                    print(f"   SMA 200: {row['sma_200']:.2f} ({sma_diff:+.2f}%)")
                
                print(f"   Reasons: {', '.join(row['reasons'])}")
        
        # High scoring WAIT signals
        wait_df = df_results[df_results['signal'] == 'WAIT'].head(10)
        
        if not wait_df.empty:
            print(f"\n{'='*80}")
            print(f"TOP {len(wait_df)} WAIT SIGNALS (High Potential)")
            print(f"{'='*80}")
            
            for idx, row in wait_df.iterrows():
                print(f"\n{row['ticker']} - Score: {row['score']} | Price: {row['close']} | RVOL: {row['rvol']}x")
        
        print(f"\n{'='*80}\n")
    
    def generate_csv_report(self, df_results: pd.DataFrame, filename: Optional[str] = None) -> str:
        """
        Generate CSV report
        
        Args:
            df_results: DataFrame with analysis results
            filename: Custom filename (default: signals_YYYYMMDD.csv)
            
        Returns:
            Path to saved CSV file
        """
        if filename is None:
            filename = f"signals_{datetime.now().strftime('%Y%m%d')}.csv"
        
        filepath = self.output_dir / filename
        
        # Prepare DataFrame for export
        export_df = df_results.copy()
        
        # Convert reasons list to string
        if 'reasons' in export_df.columns:
            export_df['reasons'] = export_df['reasons'].apply(lambda x: ' | '.join(x) if isinstance(x, list) else '')
        
        # Save to CSV
        export_df.to_csv(filepath, index=False)
        
        logger.info(f"CSV report saved to {filepath}")
        
        return str(filepath)
    
    def generate_html_report(self, df_results: pd.DataFrame, filename: Optional[str] = None) -> str:
        """
        Generate HTML report with styling
        
        Args:
            df_results: DataFrame with analysis results
            filename: Custom filename (default: signals_YYYYMMDD.html)
            
        Returns:
            Path to saved HTML file
        """
        if filename is None:
            filename = f"signals_{datetime.now().strftime('%Y%m%d')}.html"
        
        filepath = self.output_dir / filename
        
        # Prepare HTML
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>DSE Sniper - Trading Signals Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px;
        }}
        .summary {{
            background-color: white;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px 0;
        }}
        th {{
            background-color: #34495e;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .buy {{ color: #27ae60; font-weight: bold; }}
        .wait {{ color: #f39c12; font-weight: bold; }}
        .ignore {{ color: #95a5a6; }}
        .score-high {{ background-color: #d4edda; }}
        .score-medium {{ background-color: #fff3cd; }}
        .score-low {{ background-color: #f8d7da; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>DSE SNIPER - Trading Signals Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
"""
        
        # Summary section
        if not df_results.empty:
            total = len(df_results)
            buy_count = len(df_results[df_results['signal'] == 'BUY'])
            wait_count = len(df_results[df_results['signal'] == 'WAIT'])
            ignore_count = len(df_results[df_results['signal'] == 'IGNORE'])
            
            html_content += f"""
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Analyzed:</strong> {total}</p>
        <p><strong>BUY Signals:</strong> {buy_count}</p>
        <p><strong>WAIT Signals:</strong> {wait_count}</p>
        <p><strong>IGNORE Signals:</strong> {ignore_count}</p>
    </div>
"""
        
        # Table with more columns
        html_content += """
    <table>
        <thead>
            <tr>
                <th>Rank</th>
                <th>Ticker</th>
                <th>Signal</th>
                <th>Score</th>
                <th>Close</th>
                <th>Open</th>
                <th>High</th>
                <th>Low</th>
                <th>RVOL</th>
                <th>Volume</th>
                <th>Avg Vol (20d)</th>
                <th>Change %</th>
                <th>SMA 200</th>
                <th>Paid-Up Cap</th>
                <th>Reasons</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
"""
        
        # Add rows
        for rank, (idx, row) in enumerate(df_results.iterrows(), start=1):
            signal_class = row['signal'].lower()
            
            if row['score'] >= 80:
                score_class = 'score-high'
            elif row['score'] >= 45:
                score_class = 'score-medium'
            else:
                score_class = 'score-low'
            
            reasons_str = ', '.join(row['reasons']) if isinstance(row['reasons'], list) else ''
            
            # Get additional data
            open_price = row.get('open', row['close'])
            high_price = row.get('high', row['close'])
            low_price = row.get('low', row['close'])
            avg_vol = row.get('avg_volume_20', 0)
            sma_200 = row.get('sma_200', None)
            paid_up = row.get('paid_up_capital', None)
            
            sma_str = f"{sma_200:.2f}" if sma_200 else "N/A"
            paid_up_str = f"{paid_up:.1f} Cr" if paid_up else "N/A"
            
            # BUY button style
            button_style = ""
            button_text = "BUY"
            if row['signal'] == 'BUY':
                button_style = "style='background-color: #27ae60; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;'"
            elif row['signal'] == 'WAIT':
                button_style = "style='background-color: #f39c12; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;'"
                button_text = "WATCH"
            else:
                button_style = "style='background-color: #95a5a6; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer;'"
                button_text = "SKIP"
            
            html_content += f"""
            <tr class="{score_class}">
                <td>{rank}</td>
                <td><strong>{row['ticker']}</strong></td>
                <td class="{signal_class}">{row['signal']}</td>
                <td>{row['score']}</td>
                <td>{row['close']:.2f}</td>
                <td>{open_price:.2f}</td>
                <td>{high_price:.2f}</td>
                <td>{low_price:.2f}</td>
                <td>{row['rvol']:.2f}x</td>
                <td>{row['volume']:,}</td>
                <td>{avg_vol:,}</td>
                <td>{row['price_change_pct']:.2f}%</td>
                <td>{sma_str}</td>
                <td>{paid_up_str}</td>
                <td style="font-size: 0.9em;">{reasons_str}</td>
                <td><button {button_style} onclick="alert('Trading through broker required for {row['ticker']} at {row['close']:.2f} BDT')">{button_text}</button></td>
            </tr>
"""
        
        html_content += """
        </tbody>
    </table>
    
    <div class="summary">
        <p><em>DSE Sniper System - Volume Anomaly Detection</em></p>
        <p><strong>Note:</strong> This is an automated analysis. Always perform your own due diligence before trading.</p>
    </div>
</body>
</html>
"""
        
        # Save HTML file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML report saved to {filepath}")
        
        return str(filepath)
    
    def generate_all_reports(self, df_results: pd.DataFrame, print_console: bool = True) -> dict:
        """
        Generate all report formats
        
        Args:
            df_results: DataFrame with analysis results
            print_console: Whether to print console report
            
        Returns:
            Dictionary with paths to generated reports
        """
        reports = {}
        
        # Console report
        if print_console:
            self.generate_console_report(df_results)
        
        # CSV report
        if not df_results.empty:
            csv_path = self.generate_csv_report(df_results)
            reports['csv'] = csv_path
            
            # HTML report
            html_path = self.generate_html_report(df_results)
            reports['html'] = html_path
        
        return reports


if __name__ == "__main__":
    # Test report generator with sample data
    sample_data = {
        'ticker': ['GP', 'BEXIMCO', 'SQURPHARMA'],
        'status': ['success', 'success', 'success'],
        'date': ['2024-02-20', '2024-02-20', '2024-02-20'],
        'close': [286.6, 45.5, 180.3],
        'volume': [150000, 250000, 120000],
        'rvol': [3.2, 2.8, 1.5],
        'avg_volume_20': [50000, 90000, 80000],
        'price_change_pct': [1.5, 0.8, -0.5],
        'sma_200': [280.0, 50.0, 175.0],
        'paid_up_capital': [None, 45.0, 65.0],
        'score': [90, 85, 50],
        'signal': ['BUY', 'BUY', 'WAIT'],
        'reasons': [
            ['High RVOL (3.2x)', 'Quiet Accumulation', 'Above 200 SMA'],
            ['High RVOL (2.8x)', 'Quiet Accumulation', 'Low Float (45.0 Cr)'],
            ['Above 200 SMA']
        ]
    }
    
    df = pd.DataFrame(sample_data)
    
    reporter = ReportGenerator()
    reporter.generate_console_report(df)
    reports = reporter.generate_all_reports(df, print_console=False)
    
    print("\nReports generated:")
    for report_type, path in reports.items():
        print(f"  {report_type.upper()}: {path}")
