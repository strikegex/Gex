#!/bin/bash
# Quick GEX Iron Condor Launcher
# Run this every morning before trading

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 GEX IRON CONDOR STRIKE SELECTOR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Virtual environment not activated!"
    echo "Activating venv..."
    source venv/bin/activate
fi

# Step 1: Fetch latest GEX data
echo "📊 Step 1: Fetching latest GEX data from Schwab..."
python gex_fetcher_fixed.py --symbol SPX --output gex_data.json

if [ $? -ne 0 ]; then
    echo "❌ Failed to fetch GEX data. Check your Schwab API credentials."
    exit 1
fi

echo "✅ GEX data updated"
echo ""

# Step 2: Show all three risk levels
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 OPTION 1: CONSERVATIVE (Recommended for NFP/FOMC days)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python gex_iron_condor_selector.py --risk conservative

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 OPTION 2: MODERATE (Balanced risk/reward)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python gex_iron_condor_selector.py --risk moderate

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 OPTION 3: AGGRESSIVE (Higher credit, more risk)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python gex_iron_condor_selector.py --risk aggressive

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Analysis Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Next Steps:"
echo "   1. Choose your preferred risk level above"
echo "   2. Wait until 9:45 AM ET (after volatility settles)"
echo "   3. Copy strikes to ThinkorSwim"
echo "   4. Enter iron condor"
echo "   5. Set profit target at 50-70% credit"
echo "   6. Close by 3:00 PM ET"
echo ""
echo "🔄 To refresh during trading day:"
echo "   ./quick_gex_analysis.sh"
echo ""
