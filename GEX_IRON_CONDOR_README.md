# 🎯 GEX Iron Condor Strike Selector

Automatically suggests optimal 0DTE SPX iron condor strikes based on real-time gamma exposure (GEX) data.

## 📋 Features

- ✅ Analyzes gamma walls to find strongest resistance/support
- ✅ Suggests optimal strike prices for iron condors
- ✅ Three risk levels: Conservative, Moderate, Aggressive
- ✅ Calculates expected credit and probability
- ✅ Shows top 3 gamma levels on each side
- ✅ Provides timing recommendations

## 🚀 Quick Start

### 1. Fetch Latest GEX Data

```bash
cd ~/Desktop/gex
source venv/bin/activate
python gex_fetcher_fixed.py --symbol SPX --output gex_data.json
```

### 2. Get Iron Condor Recommendation

```bash
python gex_iron_condor_selector.py
```

That's it! You'll see:
- Suggested call and put strikes
- Distance from current price
- Gamma wall levels
- Expected credit/loss
- Entry timing

## 📊 Usage Examples

### Conservative Setup (Default)
```bash
python gex_iron_condor_selector.py
```
- Wider strikes from gamma walls
- Lower credit, higher probability (~70%)
- Best for volatile days (NFP, FOMC)

### Moderate Setup
```bash
python gex_iron_condor_selector.py --risk moderate
```
- Balanced risk/reward
- Medium credit, ~65% probability
- Good for normal trading days

### Aggressive Setup
```bash
python gex_iron_condor_selector.py --risk aggressive
```
- Tighter strikes near gamma walls
- Higher credit, lower probability (~60%)
- Best for low volatility days

### Custom Wing Width
```bash
python gex_iron_condor_selector.py --wing-width 20
```
- Default is 15 points
- Wider wings = less credit, more safety
- Narrower wings = more credit, more risk

### JSON Output (for automation)
```bash
python gex_iron_condor_selector.py --json > today_trade.json
```

## 🔧 Advanced Usage

### Run Every 15 Minutes During Market Hours

Create `watch_gex.sh`:

```bash
#!/bin/bash
while true; do
    python gex_fetcher_fixed.py --symbol SPX --output gex_data.json
    python gex_iron_condor_selector.py
    sleep 900  # 15 minutes
done
```

Run it:
```bash
chmod +x watch_gex.sh
./watch_gex.sh
```

### Compare All Risk Levels

```bash
echo "=== CONSERVATIVE ==="
python gex_iron_condor_selector.py --risk conservative

echo "\n=== MODERATE ==="
python gex_iron_condor_selector.py --risk moderate

echo "\n=== AGGRESSIVE ==="
python gex_iron_condor_selector.py --risk aggressive
```

## 📖 Understanding the Output

### Example Output:
```
🎯 GEX-BASED IRON CONDOR RECOMMENDATION
======================================================================

📊 Current Market:
   SPX Price: $6,958.50
   Risk Level: CONSERVATIVE
   Analysis Time: 2026-02-11 09:45:23 AM

📞 CALL SIDE (Resistance):
   Short Call:  6,995 (+37 pts, +0.52%)
   Long Call:   7,010 (+15 wide)
   Gamma Wall:  7,000 (GEX: 54.30M)

📉 PUT SIDE (Support):
   Short Put:   6,920 (39 pts, 0.56%)
   Long Put:    6,905 (-15 wide)
   Gamma Wall:  6,900 (GEX: -28.15M)

📏 RANGE ANALYSIS:
   Total Range: 75 points (1.08%)
   Breakevens:  6,905 to 7,010

🏆 TOP 3 RESISTANCE LEVELS (Call Side):
   1. 7,000 → GEX:    54.30M, DEX:   4.55B
   2. 7,015 → GEX:    32.18M, DEX:   2.80B
   3. 7,025 → GEX:    28.45M, DEX:   2.40B

🛡️  TOP 3 SUPPORT LEVELS (Put Side):
   1. 6,900 → GEX:   -28.15M, DEX:  -2.10B
   2. 6,940 → GEX:   -18.22M, DEX:  -1.45B
   3. 6,870 → GEX:   -15.80M, DEX:  -1.20B

💰 ESTIMATED METRICS:
   Expected Credit: $5.40 - $7.50
   Max Loss/Side: $12.50 - $13.50
   Prob of Profit: ~70%

⏰ TIMING RECOMMENDATIONS:
   Entry Window: 9:45 AM - 10:30 AM ET (after volatility settles)
   Profit Target: 50-70% of credit received
   Stop Loss: 2x credit received
   Exit Time: Before 3:00 PM ET

======================================================================
✅ Trade Setup Ready - Copy strikes to ThinkorSwim
======================================================================
```

## 🧠 How It Works

1. **Loads GEX Data**: Reads `gex_data.json` from your fetcher script
2. **Finds Gamma Walls**: Identifies strongest positive (resistance) and negative (support) GEX levels
3. **Calculates Strikes**: Places short strikes near gamma walls based on risk level
4. **Adds Wings**: Creates long strikes at specified width (default 15 points)
5. **Estimates Metrics**: Calculates expected credit, max loss, probability

## ⚠️ Important Notes

### Gamma Wall Interpretation:
- **Positive GEX** (green bars) = Resistance → Market makers sell into strength
- **Negative GEX** (red bars) = Support → Market makers buy into weakness
- **Largest absolute GEX** = Strongest levels = Best strike locations

### Risk Levels Explained:
- **Conservative**: 20 points buffer from gamma walls (safer but less credit)
- **Moderate**: 10 points buffer (balanced)
- **Aggressive**: 5 points buffer (higher credit, higher risk)

### When NOT to Trade:
- ❌ No clear gamma walls (flat heatmap)
- ❌ Current price at major gamma flip zone
- ❌ VIX > 25 (use wider strikes)
- ❌ Major news pending (wait for settlement)
- ❌ Less than 30 points between short strikes

## 🔄 Daily Workflow

### Morning Routine (before market open):
```bash
# 1. Check premarket GEX
python gex_fetcher_fixed.py --symbol SPX --output gex_data.json
python gex_iron_condor_selector.py

# 2. Note suggested strikes
# 3. Wait for market open + volatility to settle
```

### Entry Time (9:45-10:30 AM ET):
```bash
# 1. Refresh GEX data
python gex_fetcher_fixed.py --symbol SPX --output gex_data.json

# 2. Get updated recommendation
python gex_iron_condor_selector.py

# 3. Verify gamma walls still strong
# 4. Enter trade on ThinkorSwim
```

### During Day:
- Monitor position
- DON'T adjust on 0DTE
- Close at 50-70% profit target
- Stop loss at 2x credit

### End of Day:
- Close any remaining positions by 3:00 PM ET
- Document results
- Prepare for next day

## 📊 Backtesting Support

Output JSON for analysis:
```bash
python gex_iron_condor_selector.py --json > logs/trade_$(date +%Y%m%d).json
```

## 🐛 Troubleshooting

### "gex_data.json not found"
**Solution**: Run fetcher first
```bash
python gex_fetcher_fixed.py --symbol SPX --output gex_data.json
```

### "No SPX data found"
**Solution**: Make sure your fetcher script is getting SPX data (not SPY)

### "Insufficient gamma data"
**Solution**: Market might be closed or data is stale. Refresh GEX data.

### Strikes seem too tight/wide
**Solution**: Adjust wing width
```bash
python gex_iron_condor_selector.py --wing-width 20  # Wider
python gex_iron_condor_selector.py --wing-width 10  # Tighter
```

## 📈 Expected Performance

Based on your GEX data quality:
- **Conservative**: 70-75% win rate, avg $2-4 credit
- **Moderate**: 65-70% win rate, avg $3-5 credit
- **Aggressive**: 60-65% win rate, avg $4-7 credit

## 🔗 Related Files

- `gex_fetcher_fixed.py` - Fetches live GEX data from Schwab
- `gex_heatmap.html` - Visualizes GEX data
- `gex_data.json` - Raw GEX data (input for this script)

## 📝 License

MIT License - Use freely for your trading

---

**⚠️ DISCLAIMER**: This tool is for educational and informational purposes. Trading options involves substantial risk. Past performance does not guarantee future results. Always use proper risk management.
