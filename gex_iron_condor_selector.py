#!/usr/bin/env python3
"""
GEX-Based Iron Condor Strike Selector
Analyzes gamma exposure data to recommend optimal iron condor strikes
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class GEXIronCondorSelector:
    def __init__(self, gex_data_file: str = "gex_data.json"):
        """Initialize with GEX data file"""
        self.gex_data_file = gex_data_file
        self.data = self._load_data()

    def _load_data(self) -> Dict:
        """Load GEX data from JSON file"""
        try:
            with open(self.gex_data_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Error: {self.gex_data_file} not found!")
            print("Run: python gex_fetcher_fixed.py --symbol SPX --output gex_data.json")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"❌ Error: Invalid JSON in {self.gex_data_file}")
            sys.exit(1)

    def get_current_price(self) -> float:
        """Extract current SPX price from data"""
        # Assuming data has SPX key with current price
        if 'SPX' in self.data:
            return self.data['SPX'].get('last_price', 0)
        return 0

    def analyze_gamma_levels(self) -> Dict:
        """Analyze gamma exposure to find key support/resistance levels"""
        if 'SPX' not in self.data:
            print("❌ No SPX data found")
            return {}

        strikes_data = self.data['SPX'].get('strikes', {})

        # Convert to list of (strike, gex, dex) tuples
        gamma_levels = []
        for strike_str, values in strikes_data.items():
            try:
                strike = float(strike_str)
                gex = values.get('net_gex', 0)
                dex = values.get('net_dex', 0)
                gamma_levels.append((strike, gex, dex))
            except (ValueError, TypeError):
                continue

        # Sort by strike
        gamma_levels.sort(key=lambda x: x[0])

        return self._identify_key_levels(gamma_levels)

    def _identify_key_levels(self, gamma_levels: List[Tuple]) -> Dict:
        """Identify key resistance and support levels"""
        current_price = self.get_current_price()

        # Separate into above (resistance) and below (support)
        resistance_levels = [(s, g, d) for s, g, d in gamma_levels if s > current_price and g > 0]
        support_levels = [(s, g, d) for s, g, d in gamma_levels if s < current_price and g < 0]

        # Sort by absolute GEX value (strongest levels)
        resistance_levels.sort(key=lambda x: abs(x[1]), reverse=True)
        support_levels.sort(key=lambda x: abs(x[1]), reverse=True)

        return {
            'current_price': current_price,
            'resistance': resistance_levels[:5],  # Top 5 resistance
            'support': support_levels[:5],  # Top 5 support
        }

    def suggest_iron_condor(self, wing_width: int = 15, 
                           risk_level: str = "conservative") -> Dict:
        """
        Suggest iron condor strikes based on GEX levels

        Args:
            wing_width: Distance between short and long strikes (default 15)
            risk_level: "conservative", "moderate", or "aggressive"
        """
        levels = self.analyze_gamma_levels()
        current_price = levels['current_price']

        if not current_price:
            print("❌ Could not determine current price")
            return {}

        resistance = levels['resistance']
        support = levels['support']

        if not resistance or not support:
            print("❌ Insufficient gamma data for analysis")
            return {}

        # Risk level adjustments
        risk_params = {
            'conservative': {'call_buffer': 20, 'put_buffer': 20},
            'moderate': {'call_buffer': 10, 'put_buffer': 10},
            'aggressive': {'call_buffer': 5, 'put_buffer': 5}
        }

        params = risk_params.get(risk_level, risk_params['conservative'])

        # Find strongest resistance (for call side)
        strongest_resistance = resistance[0][0]  # Strike with highest positive GEX
        short_call = self._round_to_strike(strongest_resistance - params['call_buffer'])
        long_call = short_call + wing_width

        # Find strongest support (for put side)
        strongest_support = support[0][0]  # Strike with highest negative GEX
        short_put = self._round_to_strike(strongest_support + params['put_buffer'])
        long_put = short_put - wing_width

        # Calculate metrics
        total_range = short_call - short_put
        pct_to_call = ((short_call - current_price) / current_price) * 100
        pct_to_put = ((current_price - short_put) / current_price) * 100

        return {
            'current_price': current_price,
            'risk_level': risk_level,
            'call_side': {
                'short': short_call,
                'long': long_call,
                'width': wing_width,
                'distance_from_price': short_call - current_price,
                'pct_from_price': pct_to_call,
                'gamma_wall': strongest_resistance,
                'gamma_strength': resistance[0][1]  # GEX value
            },
            'put_side': {
                'short': short_put,
                'long': long_put,
                'width': wing_width,
                'distance_from_price': current_price - short_put,
                'pct_from_price': pct_to_put,
                'gamma_wall': strongest_support,
                'gamma_strength': support[0][1]  # GEX value
            },
            'range': {
                'total_points': total_range,
                'total_pct': (total_range / current_price) * 100
            },
            'top_resistance': resistance[:3],
            'top_support': support[:3]
        }

    def _round_to_strike(self, price: float, increment: int = 5) -> int:
        """Round price to nearest strike (default 5-point increments for SPX)"""
        return int(round(price / increment) * increment)

    def print_recommendation(self, suggestion: Dict):
        """Pretty print the iron condor recommendation"""
        if not suggestion:
            return

        print("\n" + "="*70)
        print("🎯 GEX-BASED IRON CONDOR RECOMMENDATION")
        print("="*70)

        print(f"\n📊 Current Market:")
        print(f"   SPX Price: ${suggestion['current_price']:,.2f}")
        print(f"   Risk Level: {suggestion['risk_level'].upper()}")
        print(f"   Analysis Time: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}")

        print(f"\n📞 CALL SIDE (Resistance):")
        call = suggestion['call_side']
        print(f"   Short Call:  {call['short']:,} ({call['distance_from_price']:+.0f} pts, {call['pct_from_price']:+.2f}%)")
        print(f"   Long Call:   {call['long']:,} (+{call['width']} wide)")
        print(f"   Gamma Wall:  {call['gamma_wall']:,} (GEX: {call['gamma_strength']/1e6:.2f}M)")

        print(f"\n📉 PUT SIDE (Support):")
        put = suggestion['put_side']
        print(f"   Short Put:   {put['short']:,} ({put['distance_from_price']:.0f} pts, {put['pct_from_price']:.2f}%)")
        print(f"   Long Put:    {put['long']:,} (-{put['width']} wide)")
        print(f"   Gamma Wall:  {put['gamma_wall']:,} (GEX: {put['gamma_strength']/1e6:.2f}M)")

        print(f"\n📏 RANGE ANALYSIS:")
        range_info = suggestion['range']
        print(f"   Total Range: {range_info['total_points']:.0f} points ({range_info['total_pct']:.2f}%)")
        print(f"   Breakevens:  {put['long']:,} to {call['long']:,}")

        print(f"\n🏆 TOP 3 RESISTANCE LEVELS (Call Side):")
        for i, (strike, gex, dex) in enumerate(suggestion['top_resistance'], 1):
            print(f"   {i}. {strike:,} → GEX: {gex/1e6:>8.2f}M, DEX: {dex/1e9:>6.2f}B")

        print(f"\n🛡️  TOP 3 SUPPORT LEVELS (Put Side):")
        for i, (strike, gex, dex) in enumerate(suggestion['top_support'], 1):
            print(f"   {i}. {strike:,} → GEX: {gex/1e6:>8.2f}M, DEX: {dex/1e9:>6.2f}B")

        print(f"\n💰 ESTIMATED METRICS:")
        print(f"   Expected Credit: ${(call['width'] + put['width']) * 0.18:.2f} - ${(call['width'] + put['width']) * 0.25:.2f}")
        print(f"   Max Loss/Side: ${call['width'] - 2.50:.2f} - ${call['width'] - 1.50:.2f}")
        print(f"   Prob of Profit: ~{70 if suggestion['risk_level']=='conservative' else 65 if suggestion['risk_level']=='moderate' else 60}%")

        print(f"\n⏰ TIMING RECOMMENDATIONS:")
        print(f"   Entry Window: 9:45 AM - 10:30 AM ET (after volatility settles)")
        print(f"   Profit Target: 50-70% of credit received")
        print(f"   Stop Loss: 2x credit received")
        print(f"   Exit Time: Before 3:00 PM ET")

        print("\n" + "="*70)
        print("✅ Trade Setup Ready - Copy strikes to ThinkorSwim")
        print("="*70 + "\n")

def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(
        description="GEX-based Iron Condor Strike Selector for SPX 0DTE"
    )
    parser.add_argument(
        '--data', 
        default='gex_data.json',
        help='Path to GEX data JSON file (default: gex_data.json)'
    )
    parser.add_argument(
        '--wing-width',
        type=int,
        default=15,
        help='Width of iron condor wings in points (default: 15)'
    )
    parser.add_argument(
        '--risk',
        choices=['conservative', 'moderate', 'aggressive'],
        default='conservative',
        help='Risk level for strike selection (default: conservative)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON instead of formatted text'
    )

    args = parser.parse_args()

    # Create selector
    selector = GEXIronCondorSelector(args.data)

    # Get suggestion
    suggestion = selector.suggest_iron_condor(
        wing_width=args.wing_width,
        risk_level=args.risk
    )

    if not suggestion:
        sys.exit(1)

    # Output
    if args.json:
        print(json.dumps(suggestion, indent=2))
    else:
        selector.print_recommendation(suggestion)

if __name__ == "__main__":
    main()
