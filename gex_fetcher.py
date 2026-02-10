"""
GEX Heatmap Data Fetcher + Recommendations — Schwab API (0DTE focused)
======================================================================
Fetches 0DTE + 1DTE options chain, calculates GEX per strike with
heavy 0DTE weighting. King node = highest total gamma activity.

Usage:
  python gex_fetcher.py                         # SPX + SPY + QQQ + IWM
  python gex_fetcher.py --live --interval 60    # Continuous updates
  python gex_fetcher.py --symbol SPX SPY QQQ IWM
"""

import json, time, argparse, os, sys
from datetime import datetime, date, timedelta

APP_KEY = os.environ.get("SCHWAB_APP_KEY", "YOUR_APP_KEY_HERE")
APP_SECRET = os.environ.get("SCHWAB_APP_SECRET", "YOUR_APP_SECRET_HERE")
CALLBACK_URL = os.environ.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1:8182/")
TOKEN_PATH = os.environ.get("SCHWAB_TOKEN_PATH", "schwab_token.json")
CONTRACT_MULTIPLIER = 100

# 0DTE dominates — this is what drives intraday price action
DTE_WEIGHTS = {0: 10.0, 1: 2.0}
DTE_DEFAULT_WEIGHT = 0.0  # ignore >1DTE


def get_schwab_client():
    try:
        from schwab import auth
    except ImportError:
        print("❌ pip install schwab-py httpx --break-system-packages"); sys.exit(1)
    if APP_KEY == "YOUR_APP_KEY_HERE":
        print("❌ Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET"); sys.exit(1)
    try:
        c = auth.easy_client(api_key=APP_KEY, app_secret=APP_SECRET,
                             callback_url=CALLBACK_URL, token_path=TOKEN_PATH)
        print("✅ Authenticated with Schwab"); return c
    except Exception as e:
        print(f"❌ Auth failed: {e}"); sys.exit(1)


def get_spot_price(client, symbol):
    sym = f"${symbol}" if symbol in ("SPX","NDX","RUT","DJX","VIX") else symbol
    resp = client.get_quote(sym); resp.raise_for_status()
    q = resp.json().get(sym, {}).get("quote", {})
    return float(q.get("lastPrice", q.get("closePrice", 0)))


def get_option_chain(client, symbol, expiry=None, num_strikes=60):
    sym = f"${symbol}" if symbol in ("SPX","NDX","RUT","DJX","VIX") else symbol
    kw = {"include_underlying_quote": True, "strike_count": num_strikes * 2}
    if expiry:
        d = date.fromisoformat(expiry)
        kw["from_date"] = d; kw["to_date"] = d + timedelta(days=1)
    else:
        kw["from_date"] = date.today()
        kw["to_date"] = date.today() + timedelta(days=1)  # 0DTE + 1DTE only
    resp = client.get_option_chain(sym, **kw); resp.raise_for_status()
    return resp.json()


def calculate_gex(chain, spot):
    """
    GEX per strike. 0DTE = 10× weight, 1DTE = 2×, rest = 0.
    Also tracks total_gamma (call_gex + abs(put_gex)) for king node calc.
    Stores per-strike IV and delta from nearest 0DTE contracts for premium estimation.
    """
    today = date.today()
    strikes = {}

    def ensure(strike):
        if strike not in strikes:
            strikes[strike] = dict(
                strike=strike, net_gex=0, call_gex=0, put_gex=0,
                total_gamma=0,  # call_gex + abs(put_gex) — for king node
                call_oi=0, put_oi=0, call_volume=0, put_volume=0,
                # For premium estimation — store best 0DTE contract data
                call_iv=0, put_iv=0, call_delta=0, put_delta=0,
                call_bid=0, call_ask=0, put_bid=0, put_ask=0,
            )

    def get_dte_weight(exp_key):
        try:
            parts = exp_key.split(":")
            dte = int(parts[1]) if len(parts) >= 2 else (date.fromisoformat(parts[0]) - today).days
            return DTE_WEIGHTS.get(dte, DTE_DEFAULT_WEIGHT), dte
        except:
            return DTE_DEFAULT_WEIGHT, 99

    for exp_key, smap in chain.get("callExpDateMap", {}).items():
        weight, dte = get_dte_weight(exp_key)
        for sk, contracts in smap.items():
            strike = float(sk)
            for c in contracts:
                oi = int(c.get("openInterest", 0))
                gamma = float(c.get("gamma", 0) or 0)
                vol = int(c.get("totalVolume", 0))
                ensure(strike)
                gex = oi * gamma * spot**2 * 0.01 * CONTRACT_MULTIPLIER * weight
                strikes[strike]["call_gex"] += gex
                strikes[strike]["net_gex"] += gex
                strikes[strike]["total_gamma"] += abs(gex)
                strikes[strike]["call_oi"] += oi
                strikes[strike]["call_volume"] += vol
                # Store 0DTE contract pricing data for premium estimation
                if dte <= 0:
                    strikes[strike]["call_iv"] = float(c.get("volatility", 0) or 0)
                    strikes[strike]["call_delta"] = float(c.get("delta", 0) or 0)
                    strikes[strike]["call_bid"] = float(c.get("bid", 0) or 0)
                    strikes[strike]["call_ask"] = float(c.get("ask", 0) or 0)

    for exp_key, smap in chain.get("putExpDateMap", {}).items():
        weight, dte = get_dte_weight(exp_key)
        for sk, contracts in smap.items():
            strike = float(sk)
            for c in contracts:
                oi = int(c.get("openInterest", 0))
                gamma = float(c.get("gamma", 0) or 0)
                vol = int(c.get("totalVolume", 0))
                ensure(strike)
                gex = oi * gamma * spot**2 * 0.01 * CONTRACT_MULTIPLIER * weight
                strikes[strike]["put_gex"] -= gex
                strikes[strike]["net_gex"] -= gex
                strikes[strike]["total_gamma"] += abs(gex)
                strikes[strike]["put_oi"] += oi
                strikes[strike]["put_volume"] += vol
                if dte <= 0:
                    strikes[strike]["put_iv"] = float(c.get("volatility", 0) or 0)
                    strikes[strike]["put_delta"] = float(c.get("delta", 0) or 0)
                    strikes[strike]["put_bid"] = float(c.get("bid", 0) or 0)
                    strikes[strike]["put_ask"] = float(c.get("ask", 0) or 0)

    return strikes


def filter_near_spot(strikes, spot, n=30):
    s = sorted(strikes.values(), key=lambda x: x["strike"])
    if not s: return []
    ci = min(range(len(s)), key=lambda i: abs(s[i]["strike"] - spot))
    return s[max(0, ci-n):min(len(s), ci+n+1)]


def fmt(v):
    a = abs(v); s = "-" if v < 0 else ""
    if a >= 1e9: return f"{s}${a/1e9:,.1f}B"
    if a >= 1e6: return f"{s}${a/1e6:,.1f}M"
    if a >= 1e3: return f"{s}${a/1e3:,.1f}K"
    return f"{s}${a:,.0f}"


def generate_recommendation(symbol, spot, strikes, total_net_gex):
    if not strikes:
        return {"summary": "No data", "bias": "neutral", "details": []}
    max_abs = max(abs(s["net_gex"]) for s in strikes)
    if max_abs == 0:
        return {"summary": "No significant gamma", "bias": "neutral", "details": []}

    # King = highest TOTAL gamma activity (not net)
    king = max(strikes, key=lambda s: s["total_gamma"])
    gamma_wall = max(strikes, key=lambda s: s["net_gex"])
    put_wall = min(strikes, key=lambda s: s["net_gex"])

    pos_above = sorted([s for s in strikes if s["strike"] > spot and s["net_gex"] > max_abs * 0.15], key=lambda s: s["strike"])
    pos_below = sorted([s for s in strikes if s["strike"] < spot and s["net_gex"] > max_abs * 0.15], key=lambda s: -s["strike"])
    neg_above = sorted([s for s in strikes if s["strike"] > spot and s["net_gex"] < -max_abs * 0.15], key=lambda s: s["strike"])
    neg_below = sorted([s for s in strikes if s["strike"] < spot and s["net_gex"] < -max_abs * 0.15], key=lambda s: -s["strike"])

    nearest_pos_above = pos_above[0] if pos_above else None
    nearest_pos_below = pos_below[0] if pos_below else None
    nearest_neg_above = neg_above[0] if neg_above else None
    nearest_neg_below = neg_below[0] if neg_below else None

    spot_strike = min(strikes, key=lambda s: abs(s["strike"] - spot))
    spot_gamma_ratio = spot_strike["net_gex"] / max_abs if max_abs else 0
    spot_zone = "positive" if spot_gamma_ratio > 0.08 else "negative" if spot_gamma_ratio < -0.08 else "neutral"
    profile = "positive" if total_net_gex > max_abs * 0.1 else "negative" if total_net_gex < -max_abs * 0.1 else "neutral"

    king_dist = king["strike"] - spot
    king_pct = (king_dist / spot) * 100
    king_direction = "above" if king_dist > 0 else "below" if king_dist < 0 else "at"

    bias = "range" if profile == "positive" else "trend" if profile == "negative" else "chop"
    action_items = []

    if abs(king_pct) > 0.02:
        action_items.append(f"DRIFT TARGET: {king['strike']:.1f} ({king_direction})")
    else:
        action_items.append(f"PIN ZONE: {king['strike']:.1f}")
    if nearest_pos_below:
        action_items.append(f"SUPPORT: {nearest_pos_below['strike']:.1f}")
    if nearest_pos_above:
        action_items.append(f"RESISTANCE: {nearest_pos_above['strike']:.1f}")
    if nearest_neg_above:
        action_items.append(f"BREAKOUT ↑: {nearest_neg_above['strike']:.1f}")
    if nearest_neg_below:
        action_items.append(f"BREAKDOWN ↓: {nearest_neg_below['strike']:.1f}")

    upper = nearest_pos_above["strike"] if nearest_pos_above else (king["strike"] if king_dist > 0 else spot + 20)
    lower = nearest_pos_below["strike"] if nearest_pos_below else (king["strike"] if king_dist < 0 else spot - 20)

    if profile == "positive" and abs(king_pct) < 0.15:
        summary = f"PIN & CHOP — King {king['strike']:.1f}, +gamma. Fade in {lower:.1f}–{upper:.1f}."
    elif profile == "positive":
        summary = f"DRIFT TO KING — Magnet {king['strike']:.1f}. Range {lower:.1f}–{upper:.1f}."
    elif profile == "negative" and king_dist > 0:
        summary = f"BULLISH MOMENTUM — King pulls UP to {king['strike']:.1f}."
    elif profile == "negative" and king_dist < 0:
        summary = f"BEARISH MOMENTUM — King pulls DOWN to {king['strike']:.1f}."
    elif profile == "negative":
        summary = f"VOLATILE — Big moves expected. King {king['strike']:.1f}."
    else:
        summary = f"CHOPPY — Neutral. King {king['strike']:.1f}. Wait."

    return {
        "summary": summary, "bias": bias, "profile": profile, "spot_zone": spot_zone,
        "king_node": {"strike": king["strike"], "gex": king["net_gex"],
                      "total_gamma": king["total_gamma"],
                      "direction": king_direction, "distance": king_dist, "distance_pct": king_pct},
        "gamma_wall": {"strike": gamma_wall["strike"], "gex": gamma_wall["net_gex"]},
        "put_wall": {"strike": put_wall["strike"], "gex": put_wall["net_gex"]},
        "expected_range": {"low": lower, "high": upper, "width": upper - lower, "width_pct": (upper-lower)/spot*100},
        "support": {"strike": nearest_pos_below["strike"], "gex": nearest_pos_below["net_gex"]} if nearest_pos_below else None,
        "resistance": {"strike": nearest_pos_above["strike"], "gex": nearest_pos_above["net_gex"]} if nearest_pos_above else None,
        "breakout_above": {"strike": nearest_neg_above["strike"], "gex": nearest_neg_above["net_gex"]} if nearest_neg_above else None,
        "breakdown_below": {"strike": nearest_neg_below["strike"], "gex": nearest_neg_below["net_gex"]} if nearest_neg_below else None,
        "details": [], "action_items": action_items,
        "timestamp": datetime.now().isoformat(),
    }


def fetch_gex(client, symbol, expiry=None, num_strikes=30):
    print(f"\n{'='*60}\n  {symbol} — Fetching 0DTE GEX...\n{'='*60}")
    spot = get_spot_price(client, symbol)
    print(f"  Spot: ${spot:,.2f}")

    chain = get_option_chain(client, symbol, expiry, num_strikes)
    underlying = chain.get("underlying", {})
    if underlying and underlying.get("last"):
        spot = float(underlying["last"])

    expirations = sorted(set([e.split(":")[0] for e in
        list(chain.get("callExpDateMap", {}).keys()) + list(chain.get("putExpDateMap", {}).keys())]))
    print(f"  Expirations: {', '.join(expirations[:4])}")

    all_strikes = calculate_gex(chain, spot)
    filtered = filter_near_spot(all_strikes, spot, num_strikes)

    total = sum(s["net_gex"] for s in filtered)
    gw = max(filtered, key=lambda s: s["net_gex"])
    pw = min(filtered, key=lambda s: s["net_gex"])
    king = max(filtered, key=lambda s: s["total_gamma"])

    rec = generate_recommendation(symbol, spot, filtered, total)
    print(f"  {rec['summary']}")
    for item in rec["action_items"]:
        print(f"    → {item}")

    return {
        "symbol": symbol, "spot": spot,
        "timestamp": datetime.now().isoformat(),
        "expirations": expirations, "total_net_gex": total,
        "gamma_wall": gw["strike"], "put_wall": pw["strike"],
        "king_node": king["strike"], "strikes": filtered,
        "recommendation": rec,
    }


def run_live(client, symbols, expiry, interval, output):
    print(f"\n🔴 LIVE — every {interval}s | {', '.join(symbols)} | Ctrl+C to stop\n")
    while True:
        try:
            data = {}
            for sym in symbols:
                data[sym] = fetch_gex(client, sym, expiry)
            with open(output, "w") as f:
                json.dump(data, f, indent=2)
            print(f"\n✅ Saved {output} at {datetime.now().strftime('%H:%M:%S')}")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n🛑 Stopped."); break
        except Exception as e:
            print(f"⚠️ {e} — retrying in {interval}s"); time.sleep(interval)


def main():
    p = argparse.ArgumentParser(description="GEX Fetcher (Schwab 0DTE)")
    p.add_argument("--symbol", nargs="+", default=["SPX", "SPY", "QQQ", "IWM"])
    p.add_argument("--expiry", type=str, default=None)
    p.add_argument("--strikes", type=int, default=30)
    p.add_argument("--output", type=str, default="gex_data.json")
    p.add_argument("--live", action="store_true")
    p.add_argument("--interval", type=int, default=60)
    args = p.parse_args()
    client = get_schwab_client()
    if args.live:
        run_live(client, args.symbol, args.expiry, args.interval, args.output)
    else:
        data = {}
        for sym in args.symbol:
            data[sym] = fetch_gex(client, sym, args.expiry, args.strikes)
        with open(args.output, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\n✅ Saved to {args.output}")


if __name__ == "__main__":
    main()
