#!/bin/bash
# Simple GEX Analysis - Conservative Only
echo "🎯 Fetching GEX data and analyzing..."
python gex_fetcher_fixed.py --symbol SPX --output gex_data.json && \
python gex_iron_condor_selector.py --risk conservative
