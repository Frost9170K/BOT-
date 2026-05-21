"""
=============================================================
  BOT DE TRADING v9 — 25 INDICADORES
=============================================================
  NOVO no v8: Ichimoku, CMF, CCI, HMA, Pivot Points, Williams %R
  ✅ Order Book Imbalance (Binance grátis) — detecta pressão real
  ✅ Bid/Ask Spread filter — bloqueia entradas em ativos ilíquidos
  ✅ VWAP como âncora de entrada e suporte/resistência
  ✅ Alertas Telegram em tempo real (trades, circuit breakers, status)
  ✅ Grid Trading adaptativo em mercado SIDEWAYS
  ✅ Slippage realista no paper trading (0.1% líquidos, 0.3% outros)
  ✅ Sortino Ratio (melhor que Sharpe para crypto)
  ✅ Profit Factor (lucro bruto / perda bruta)
  ✅ Expectancy por trade
  ✅ Walk-forward backtesting (70/15/15 train/val/test)
  ✅ Métricas completas de performance no status

  MANTIDO do v6:
  ✅ Kelly Criterion + Partial TP (TP1/TP2/TP3) + Breakeven SL
  ✅ Correlation Guard + Consecutive Loss CB + Time-Based Exit
  ✅ VaR + ATR sizing + 17 indicadores com votação
  ✅ Supertrend + SAR + ADX + StochRSI + RSI Div + OBV + CVD
  ✅ Fear & Greed + Funding Rate + OI + L/S + CryptoPanic
  ✅ Circuit breakers global/diário/semanal
  ✅ Auto-otimização + Auto-pesquisa semanais
=============================================================

INSTALAÇÃO:
  pip install requests anthropic colorama schedule

VARIÁVEIS DE AMBIENTE:
  BINANCE_API_KEY, BINANCE_API_SECRET, CLAUDE_API_KEY
  (Telegram removido nesta versão)

  CRYPTOPANIC_TOKEN (opcional, grátis em cryptopanic.com)

COMO RODAR:
  python trading_bot_v9.py              # paper trading
  python trading_bot_v9.py --live       # live trading
  python trading_bot_v9.py --backtest   # walk-forward backtest
  python trading_bot_v9.py --research   # pesquisa melhorias
  python trading_bot_v9.py --optimize   # otimiza parâmetros
  python trading_bot_v9.py --status     # status do portfólio

CONFIGURAÇÃO DO TELEGRAM:
  1. Abra o Telegram e procure @BotFather
  2. Envie /newbot e siga as instruções
  3. Copie o token gerado
  4. Procure @userinfobot e envie /start para obter seu chat_id
  5. Configure TELEGRAM_TOKEN e TELEGRAM_CHAT_ID nas variáveis
=============================================================
"""

import os, sys, json, time, hmac, hashlib, logging, requests, schedule, argparse, math
from datetime import datetime, timedelta
from urllib.parse import urlencode
from colorama import Fore, init

init(autoreset=True)

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
BINANCE_API_KEY      = os.environ.get("BINANCE_API_KEY",      "SUA_BINANCE_API_KEY")
BINANCE_API_SECRET   = os.environ.get("BINANCE_API_SECRET",   "SUA_BINANCE_API_SECRET")
CLAUDE_API_KEY       = os.environ.get("CLAUDE_API_KEY",       "SUA_CLAUDE_API_KEY")
TELEGRAM_TOKEN       = os.environ.get("TELEGRAM_TOKEN",       "")
TELEGRAM_CHAT_ID     = os.environ.get("TELEGRAM_CHAT_ID",     "")
CRYPTOPANIC_TOKEN    = os.environ.get("CRYPTOPANIC_TOKEN",    "")

INTERVAL_MINUTES     = 30
PAPER_BALANCE        = 1000.0
CAPITAL_PER_TRADE    = 0.08
MAX_POSITIONS        = 5
MAX_CORRELATED       = 3
STOP_LOSS_PCT        = 0.08
TP1_PCT              = 0.10
TP2_PCT              = 0.20
TP3_PCT              = 0.35
TRAILING_STOP_PCT    = 0.05
MIN_SCORE            = 7
MIN_VOTE_SCORE       = 5
MAX_DRAWDOWN_PCT     = 0.15
MAX_DAILY_LOSS_PCT   = 0.05
MAX_WEEKLY_LOSS_PCT  = 0.08
MAX_CONSEC_LOSSES    = 3
TIME_EXIT_HOURS      = 72
DCA_TRIGGER_PCT      = 0.05
DCA_MAX_TIMES        = 2
ADX_MIN_TREND        = 20
MAX_ATR_PCT          = 6.0
OPTIMIZE_DAYS        = 7
RESEARCH_DAYS        = 7

# Order Book
MAX_SPREAD_PCT       = 1.5         # bloqueia entrada se spread > 1.5%
MIN_OB_IMBALANCE     = 0.15        # mín. imbalance positivo para sinal de compra
OB_DEPTH_LEVELS      = 20          # níveis do order book a analisar

# Grid Trading (ativo em regime SIDEWAYS)
GRID_LEVELS          = 5           # número de níveis do grid
GRID_SPACING_PCT     = 0.02        # espaçamento base entre níveis (2%)
GRID_AMOUNT_PCT      = 0.04        # capital por nível do grid (4%)

# Slippage realista no paper trading
SLIPPAGE_LIQUID      = 0.001       # 0.1% para pares líquidos (top 5)
SLIPPAGE_NORMAL      = 0.003       # 0.3% para demais altcoins
LIQUID_PAIRS         = {"LINK", "ATOM", "NEAR", "AAVE", "UNI"}

WATCHLIST = [
    # Majors — adicionados no v9
    "BTC","ETH",
    # Altcoins estabelecidas
    "AAVE","UNI","LINK","GRT","FIL",
    "NEAR","ATOM","INJ","RENDER","FET",
    "OCEAN","AR","ICP","RUNE","OP"
]

CORRELATION_GROUPS = {
    "majors": ["BTC","ETH"],           # grupo novo
    "defi":   ["AAVE","UNI","GRT"],
    "layer1": ["NEAR","ATOM","FIL","ICP"],
    "ai":     ["RENDER","FET","OCEAN"],
    "layer2": ["OP","INJ"],
    "other":  ["LINK","RUNE","AR"]
}

# Arbitragem triangular — pares a escanear na Binance
# Formato: (base, intermediate, quote) — sempre começa e termina em USDT
ARB_TRIANGLES = [
    ("BTC", "ETH",  "USDT"),   # USDT→BTC→ETH→USDT
    ("BTC", "BNB",  "USDT"),
    ("BTC", "SOL",  "USDT"),
    ("ETH", "BNB",  "USDT"),
    ("ETH", "SOL",  "USDT"),
    ("BTC", "LINK", "USDT"),
    ("ETH", "LINK", "USDT"),
    ("BTC", "NEAR", "USDT"),
    ("ETH", "ATOM", "USDT"),
    ("BTC", "ATOM", "USDT"),
]
ARB_MIN_PROFIT_PCT = 0.15   # % mínimo de lucro líquido (após taxas) para alertar
ARB_FEE_PCT        = 0.001  # 0.1% por trade (Binance padrão)
ARB_ENABLED        = True   # False para desativar o scanner

# Watchlist dinâmica — ativos com bom histórico sobem, ruins descem
DYNAMIC_WATCHLIST_ENABLED = True
DYNAMIC_MAX_SIZE          = 20   # máximo de ativos na watchlist dinâmica
ASSET_SCORE_FILE          = "bot_v9_asset_scores.json"

STATE_FILE    = "bot_v9_state.json"
OPTIMIZE_FILE = "bot_v9_optimize.json"
RESEARCH_FILE = "bot_v9_research.json"
# ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler("bot_v9.log", encoding="utf-8"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════
#  TELEGRAM ALERTS
# ══════════════════════════════════════════

def tg(msg: str, silent: bool = False):
    """Envia mensagem para o Telegram. Silent=True para alertas de baixa prioridade."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML",
                  "disable_notification": silent},
            timeout=5
        )
    except Exception as e:
        log.warning(f"Telegram: {e}")

def tg_trade(action, symbol, price, amount, reason, pnl_pct=None):
    emoji = "🟢" if action == "BUY" else "🔴"
    pnl_str = f"\n📊 P&amp;L: <b>{pnl_pct:+.1f}%</b>" if pnl_pct else ""
    msg = (f"{emoji} <b>{action} {symbol}</b>\n"
           f"💰 Preço: <b>${price:.4f}</b>\n"
           f"💵 Valor: <b>${amount:.2f}</b>"
           f"{pnl_str}\n"
           f"📝 {reason}")
    tg(msg)

def tg_alert(title, msg, urgent=False):
    emoji = "🚨" if urgent else "⚠️"
    tg(f"{emoji} <b>{title}</b>\n{msg}", silent=not urgent)

def tg_status(state, portfolio_val, pnl_pct, sharpe, sortino, profit_factor, winrate):
    pos_lines = ""
    for sym, pos in state["positions"].items():
        cur = get_price(sym) or pos["entry_price"]
        pnl = ((cur - pos["entry_price"]) / pos["entry_price"]) * 100
        pos_lines += f"\n  {'🟢' if pnl>=0 else '🔴'} {sym}: {pnl:+.1f}%"
    msg = (f"📊 <b>STATUS DO PORTFÓLIO</b>\n"
           f"💼 Valor: <b>${portfolio_val:,.2f}</b>\n"
           f"📈 P&amp;L: <b>{pnl_pct:+.2f}%</b>\n"
           f"📐 Sharpe: <b>{sharpe:.2f}</b> | Sortino: <b>{sortino:.2f}</b>\n"
           f"💡 Profit Factor: <b>{profit_factor:.2f}</b> | WR: <b>{winrate:.0f}%</b>\n"
           f"🔢 Posições: <b>{len(state['positions'])}</b>{pos_lines}")
    tg(msg, silent=True)


# ══════════════════════════════════════════
#  BINANCE API
# ══════════════════════════════════════════

def b_get(path, params={}, base="https://api.binance.com"):
    try:
        r = requests.get(f"{base}{path}", params=params, timeout=8)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        log.warning(f"GET {path}: {e}"); return None

def b_signed(method, path, params={}):
    try:
        params["timestamp"] = int(time.time() * 1000)
        q = urlencode(params)
        sig = hmac.new(BINANCE_API_SECRET.encode(), q.encode(), hashlib.sha256).hexdigest()
        r = requests.request(method, f"https://api.binance.com{path}?{q}&signature={sig}",
                             headers={"X-MBX-APIKEY": BINANCE_API_KEY}, timeout=10)
        return r.json() if r.status_code in (200, 201) else None
    except Exception as e:
        log.error(f"Signed {path}: {e}"); return None

def get_price(sym):
    d = b_get("/api/v3/ticker/price", {"symbol": f"{sym}USDT"})
    return float(d["price"]) if d else None

def get_klines(sym, interval="4h", limit=150):
    data = b_get("/api/v3/klines", {"symbol": f"{sym}USDT", "interval": interval, "limit": limit})
    if not data: return []
    return [{"open": float(c[1]), "high": float(c[2]), "low": float(c[3]),
             "close": float(c[4]), "volume": float(c[5]), "open_time": c[0]} for c in data]

def get_ticker_24h(sym):
    d = b_get("/api/v3/ticker/24hr", {"symbol": f"{sym}USDT"})
    if not d: return {}
    return {"price": float(d.get("lastPrice", 0)), "change_24h": float(d.get("priceChangePercent", 0)),
            "volume_24h": float(d.get("quoteVolume", 0))}

FAPI = "https://fapi.binance.com"

def get_funding_rate(sym):
    try:
        d = b_get("/fapi/v1/premiumIndex", {"symbol": f"{sym}USDT"}, FAPI)
        if d:
            fr = float(d.get("lastFundingRate", 0)) * 100
            return {"rate": round(fr, 4), "signal": "EXTREME_LONG" if fr > 0.05 else "EXTREME_SHORT" if fr < -0.05 else "NEUTRAL"}
    except: pass
    return {"rate": 0, "signal": "NEUTRAL"}

def get_open_interest(sym):
    try:
        cur = b_get("/fapi/v1/openInterest", {"symbol": f"{sym}USDT"}, FAPI)
        his = b_get("/futures/data/openInterestHist", {"symbol": f"{sym}USDT", "period": "4h", "limit": 10}, FAPI)
        if cur and his:
            oi_now = float(cur.get("openInterest", 0))
            oi_prev = float(his[0].get("sumOpenInterest", oi_now))
            chg = round(((oi_now - oi_prev) / oi_prev) * 100, 2) if oi_prev else 0
            return {"oi": oi_now, "change_pct": chg, "trend": "INCREASING" if chg > 2 else "DECREASING" if chg < -2 else "STABLE"}
    except: pass
    return {"oi": 0, "change_pct": 0, "trend": "STABLE"}

def get_long_short_ratio(sym):
    try:
        d = b_get("/futures/data/globalLongShortAccountRatio",
                  {"symbol": f"{sym}USDT", "period": "4h", "limit": 1}, FAPI)
        if d and len(d) > 0:
            lp = round(float(d[0].get("longAccount", 0.5)) * 100, 1)
            return {"long_pct": lp, "signal": "EXTREME_LONG" if lp > 70 else "EXTREME_SHORT" if lp < 30 else "BALANCED"}
    except: pass
    return {"long_pct": 50.0, "signal": "BALANCED"}


# ══════════════════════════════════════════
#  ORDER BOOK — IMBALANCE E SPREAD
# ══════════════════════════════════════════

def get_order_book_data(sym: str) -> dict:
    """
    Busca order book e calcula:
    - Spread bid/ask em %
    - Imbalance: (bid_vol - ask_vol) / (bid_vol + ask_vol)
    - Sinal: BULLISH se bid volume muito maior que ask
    """
    try:
        data = b_get("/api/v3/depth", {"symbol": f"{sym}USDT", "limit": OB_DEPTH_LEVELS})
        if not data:
            return {"spread_pct": 0, "imbalance": 0, "signal": "NEUTRAL",
                    "bid_vol": 0, "ask_vol": 0, "best_bid": 0, "best_ask": 0}

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        if not bids or not asks:
            return {"spread_pct": 0, "imbalance": 0, "signal": "NEUTRAL",
                    "bid_vol": 0, "ask_vol": 0, "best_bid": 0, "best_ask": 0}

        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])

        # Spread percentual
        spread_pct = round(((best_ask - best_bid) / best_bid) * 100, 4) if best_bid else 0

        # Volume acumulado dos N melhores níveis
        bid_vol = sum(float(b[1]) for b in bids[:OB_DEPTH_LEVELS])
        ask_vol = sum(float(a[1]) for a in asks[:OB_DEPTH_LEVELS])
        total_vol = bid_vol + ask_vol

        # Imbalance: vai de -1 (pressure vendedora) a +1 (pressure compradora)
        imbalance = round((bid_vol - ask_vol) / total_vol, 4) if total_vol else 0

        signal = ("STRONG_BUY" if imbalance > 0.3 else
                  "BUY"        if imbalance > MIN_OB_IMBALANCE else
                  "SELL"       if imbalance < -MIN_OB_IMBALANCE else
                  "NEUTRAL")

        return {
            "spread_pct":  spread_pct,
            "imbalance":   imbalance,
            "signal":      signal,
            "bid_vol":     round(bid_vol, 2),
            "ask_vol":     round(ask_vol, 2),
            "best_bid":    best_bid,
            "best_ask":    best_ask,
        }
    except Exception as e:
        log.warning(f"Order book {sym}: {e}")
        return {"spread_pct": 0, "imbalance": 0, "signal": "NEUTRAL",
                "bid_vol": 0, "ask_vol": 0, "best_bid": 0, "best_ask": 0}


# ══════════════════════════════════════════
#  VWAP — Volume Weighted Average Price
# ══════════════════════════════════════════

def calc_vwap(candles: list) -> dict:
    """
    VWAP = Σ(típico * volume) / Σ(volume)
    Usado como âncora de suporte/resistência e confirmação de entrada.
    """
    if len(candles) < 2:
        return {"vwap": 0, "position": "UNKNOWN", "deviation_pct": 0}

    total_tp_vol = 0; total_vol = 0
    for c in candles[-24:]:  # últimas 24 velas (1 dia em 1h ou 4 dias em 4h)
        typical = (c["high"] + c["low"] + c["close"]) / 3
        total_tp_vol += typical * c["volume"]
        total_vol += c["volume"]

    vwap = total_tp_vol / total_vol if total_vol else candles[-1]["close"]
    price = candles[-1]["close"]
    dev_pct = round(((price - vwap) / vwap) * 100, 2) if vwap else 0

    position = ("ABOVE_VWAP"  if price > vwap * 1.01 else
                "BELOW_VWAP"  if price < vwap * 0.99 else
                "AT_VWAP")

    return {"vwap": round(vwap, 6), "position": position, "deviation_pct": dev_pct}


# ══════════════════════════════════════════
#  FEAR & GREED
# ══════════════════════════════════════════

def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=6)
        if r.status_code == 200:
            d = r.json()["data"][0]; v = int(d["value"])
            return {"value": v, "label": d["value_classification"],
                    "regime": ("EXTREME_FEAR" if v <= 25 else "FEAR" if v <= 45 else
                               "NEUTRAL" if v <= 55 else "GREED" if v <= 75 else "EXTREME_GREED")}
    except: pass
    return {"value": 50, "label": "Neutral", "regime": "NEUTRAL"}


# ══════════════════════════════════════════
#  CRYPTOPANIC
# ══════════════════════════════════════════

def get_news_sentiment(symbol):
    if not CRYPTOPANIC_TOKEN:
        return {"score": 0, "signal": "NEUTRAL", "news_count": 0}
    coin_map = {"AAVE": "aave", "UNI": "uniswap", "LINK": "chainlink", "GRT": "the-graph",
                "FIL": "filecoin", "NEAR": "near-protocol", "ATOM": "cosmos",
                "INJ": "injective-protocol", "RENDER": "render-token", "FET": "fetch-ai",
                "OCEAN": "ocean-protocol", "AR": "arweave", "ICP": "internet-computer",
                "RUNE": "thorchain", "OP": "optimism"}
    try:
        r = requests.get("https://cryptopanic.com/api/v1/posts/",
            params={"auth_token": CRYPTOPANIC_TOKEN, "currencies": coin_map.get(symbol, symbol.lower()),
                    "filter": "hot", "kind": "news", "limit": 10}, timeout=8)
        if r.status_code != 200:
            return {"score": 0, "signal": "NEUTRAL", "news_count": 0}
        results = r.json().get("results", [])
        if not results:
            return {"score": 0, "signal": "NEUTRAL", "news_count": 0}
        bullish = sum(p.get("votes", {}).get("positive", 0) for p in results)
        bearish = sum(p.get("votes", {}).get("negative", 0) for p in results)
        total = bullish + bearish
        score = round(((bullish - bearish) / total) * 10, 1) if total > 0 else 0
        return {"score": score, "signal": "BULLISH" if score > 2 else "BEARISH" if score < -2 else "NEUTRAL",
                "news_count": len(results)}
    except Exception as e:
        log.warning(f"CryptoPanic {symbol}: {e}")
        return {"score": 0, "signal": "NEUTRAL", "news_count": 0}


# ══════════════════════════════════════════
#  INDICADORES TÉCNICOS
# ══════════════════════════════════════════

def calc_rsi(closes, period=14):
    if len(closes) < period + 1: return 50.0
    gains, losses = [], []
    for i in range(1, period + 1):
        d = closes[-period + i] - closes[-period + i - 1]
        (gains if d > 0 else losses).append(abs(d))
    ag = sum(gains) / period if gains else 0
    al = sum(losses) / period if losses else 0.0001
    return round(100 - (100 / (1 + ag / al)), 2)

def calc_ema(closes, period):
    if len(closes) < period: return closes[-1] if closes else 0
    k, e = 2 / (period + 1), sum(closes[:period]) / period
    for p in closes[period:]: e = p * k + e * (1 - k)
    return round(e, 8)

def calc_macd(closes):
    if len(closes) < 26: return {"macd": 0, "signal": 0, "histogram": 0}
    mv = calc_ema(closes, 12) - calc_ema(closes, 26)
    hist = [calc_ema(closes[:i], 12) - calc_ema(closes[:i], 26) for i in range(26, len(closes) + 1)]
    sig = calc_ema(hist, 9) if len(hist) >= 9 else mv
    return {"macd": round(mv, 8), "signal": round(sig, 8), "histogram": round(mv - sig, 8)}

def calc_bollinger(closes, period=20):
    if len(closes) < period:
        p = closes[-1] if closes else 0
        return {"upper": p, "middle": p, "lower": p, "width": 0, "percent_b": 0.5}
    w = closes[-period:]; mid = sum(w) / period
    std = (sum((x - mid) ** 2 for x in w) / period) ** 0.5
    up, lo = mid + 2 * std, mid - 2 * std
    pct_b = round((closes[-1] - lo) / (up - lo), 3) if (up - lo) else 0.5
    return {"upper": round(up, 8), "middle": round(mid, 8), "lower": round(lo, 8),
            "width": round(((up - lo) / mid) * 100, 2) if mid else 0, "percent_b": pct_b}

def calc_atr(candles, period=14):
    if len(candles) < period + 1: return 0.0
    trs = [max(c["high"] - c["low"], abs(c["high"] - candles[i-1]["close"]),
               abs(c["low"] - candles[i-1]["close"])) for i, c in enumerate(candles) if i > 0]
    return round(sum(trs[-period:]) / period, 8)

def calc_supertrend(candles, period=10, multiplier=3.0):
    if len(candles) < period + 1: return {"signal": "NEUTRAL", "value": 0, "is_uptrend": None}
    atr = calc_atr(candles, period)
    if atr == 0: return {"signal": "NEUTRAL", "value": 0, "is_uptrend": None}
    hl2 = (candles[-1]["high"] + candles[-1]["low"]) / 2
    lo_band = hl2 - multiplier * atr
    is_up = candles[-1]["close"] > lo_band
    prev = candles[-2]["close"]
    sig = ("BUY" if is_up and prev <= lo_band else "SELL" if not is_up and prev >= hl2 + multiplier * atr
           else "UP" if is_up else "DOWN")
    return {"signal": sig, "value": round(lo_band if is_up else hl2 + multiplier * atr, 8), "is_uptrend": is_up}

def calc_parabolic_sar(candles, start=0.02, increment=0.02, maximum=0.2):
    if len(candles) < 5: return {"signal": "NEUTRAL", "sar": 0, "is_uptrend": True}
    highs = [c["high"] for c in candles]; lows = [c["low"] for c in candles]; closes = [c["close"] for c in candles]
    af = start; uptrend = closes[1] >= closes[0]; ep = highs[0] if uptrend else lows[0]
    sar = lows[0] if uptrend else highs[0]
    for i in range(2, len(candles)):
        if uptrend:
            sar = min(sar + af * (ep - sar), lows[i-1], lows[i-2])
            if lows[i] < sar: uptrend = False; sar = ep; ep = lows[i]; af = start
            elif highs[i] > ep: ep = highs[i]; af = min(af + increment, maximum)
        else:
            sar = max(sar + af * (ep - sar), highs[i-1], highs[i-2])
            if highs[i] > sar: uptrend = True; sar = ep; ep = highs[i]; af = start
            elif lows[i] < ep: ep = lows[i]; af = min(af + increment, maximum)
    return {"signal": "BUY" if uptrend else "SELL", "sar": round(sar, 8), "is_uptrend": uptrend}

def calc_adx(candles, period=14):
    if len(candles) < period + 2:
        return {"adx": 0, "plus_di": 0, "minus_di": 0, "trend_strength": "WEAK"}
    highs = [c["high"] for c in candles]; lows = [c["low"] for c in candles]; closes = [c["close"] for c in candles]
    trs, pdms, mdms = [], [], []
    for i in range(1, len(candles)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        up = highs[i] - highs[i-1]; dn = lows[i-1] - lows[i]
        pdms.append(up if up > dn and up > 0 else 0)
        mdms.append(dn if dn > up and dn > 0 else 0)
        trs.append(tr)
    atr14 = sum(trs[-period:]) / period
    if atr14 == 0: return {"adx": 0, "plus_di": 0, "minus_di": 0, "trend_strength": "WEAK"}
    pdi = round(100 * sum(pdms[-period:]) / period / atr14, 2)
    mdi = round(100 * sum(mdms[-period:]) / period / atr14, 2)
    dx = abs(pdi - mdi) / (pdi + mdi) * 100 if (pdi + mdi) > 0 else 0
    adx = round(dx, 2)
    return {"adx": adx, "plus_di": pdi, "minus_di": mdi,
            "trend_strength": "STRONG" if adx > 40 else "TRENDING" if adx > ADX_MIN_TREND else "WEAK"}

def calc_stochastic_rsi(closes, period=14):
    if len(closes) < period * 2: return {"k": 50, "d": 50, "signal": "NEUTRAL"}
    rsi_vals = [calc_rsi(closes[:i], period) for i in range(period, len(closes) + 1)]
    if len(rsi_vals) < period: return {"k": 50, "d": 50, "signal": "NEUTRAL"}
    rw = rsi_vals[-period:]; mn, mx = min(rw), max(rw)
    k = round(((rsi_vals[-1] - mn) / (mx - mn) * 100) if (mx - mn) else 50, 2)
    return {"k": k, "d": k, "signal": "OVERSOLD" if k < 20 else "OVERBOUGHT" if k > 80 else "NEUTRAL"}

def calc_obv(candles):
    if len(candles) < 2: return {"obv": 0, "trend": "NEUTRAL"}
    obv = 0
    for i in range(1, len(candles)):
        if candles[i]["close"] > candles[i-1]["close"]: obv += candles[i]["volume"]
        elif candles[i]["close"] < candles[i-1]["close"]: obv -= candles[i]["volume"]
    obv_p = 0
    for i in range(1, max(1, len(candles) - 5)):
        if candles[i]["close"] > candles[i-1]["close"]: obv_p += candles[i]["volume"]
        elif candles[i]["close"] < candles[i-1]["close"]: obv_p -= candles[i]["volume"]
    return {"obv": round(obv, 0), "trend": "RISING" if obv > obv_p else "FALLING"}

def detect_rsi_divergence(candles, closes):
    if len(candles) < 20 or len(closes) < 20:
        return {"bullish": False, "bearish": False}
    min_r = min(c["low"] for c in candles[-10:])
    min_e = min(c["low"] for c in candles[-20:-10])
    rsi_r = calc_rsi(closes[-10:]); rsi_e = calc_rsi(closes[-20:-10])
    return {"bullish": min_r < min_e and rsi_r > rsi_e,
            "bearish": min_r > min_e and rsi_r < rsi_e}

def calc_cvd(candles):
    if len(candles) < 10: return {"cvd": 0, "trend": "NEUTRAL"}
    cvd = 0
    for c in candles[-20:]:
        body = c["close"] - c["open"]; hl = c["high"] - c["low"] + 0.0001
        cvd += (c["volume"] * (body / hl) if body > 0 else -c["volume"] * (abs(body) / hl))
    return {"cvd": round(cvd, 2), "trend": "BULLISH" if cvd > 0 else "BEARISH"}

def calc_fibonacci(candles):
    if len(candles) < 20: return {"level": 0.5, "zone": "UNKNOWN"}
    hi = max(c["high"] for c in candles[-20:]); lo = min(c["low"] for c in candles[-20:])
    p = candles[-1]["close"]; rng = hi - lo
    if rng == 0: return {"level": 0.5, "zone": "UNKNOWN"}
    ratio = (hi - p) / rng
    zone = ("SUPPORT_618" if 0.56 < ratio < 0.66 else "SUPPORT_382" if 0.33 < ratio < 0.43
            else "RESISTANCE" if ratio < 0.1 else "NEUTRAL")
    return {"level": round(ratio, 3), "zone": zone}

def calc_volume_ratio(volumes, period=20):
    if len(volumes) < period + 1: return 1.0
    avg = sum(volumes[-period-1:-1]) / period
    return round(volumes[-1] / avg, 2) if avg else 1.0

def calc_var(closes, confidence=0.95):
    if len(closes) < 30: return STOP_LOSS_PCT
    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
    returns.sort()
    idx = int((1 - confidence) * len(returns))
    return min(max(abs(returns[idx]) * math.sqrt(1), 0.03), 0.15)

def detect_market_regime(btc_candles):
    if len(btc_candles) < 50: return "UNKNOWN"
    closes = [c["close"] for c in btc_candles]
    e20, e50, rsi = calc_ema(closes, 20), calc_ema(closes, 50), calc_rsi(closes)
    p = closes[-1]
    if p > e20 > e50 and rsi > 50: return "BULL"
    elif p < e20 < e50 and rsi < 50: return "BEAR"
    return "SIDEWAYS"


# ══════════════════════════════════════════
#  NOVOS INDICADORES v8
# ══════════════════════════════════════════

def calc_ichimoku(candles: list) -> dict:
    """
    Ichimoku Kinko Hyo — sistema completo de tendência, suporte e resistência.
    Tenkan-sen (9): linha de conversão
    Kijun-sen (26): linha base
    Senkou Span A: média das duas anteriores, projetada 26 períodos à frente
    Senkou Span B: média de 52 períodos, projetada 26 à frente
    Chikou Span: preço atual plotado 26 períodos atrás
    """
    if len(candles) < 52:
        return {"signal": "NEUTRAL", "above_cloud": None, "cloud_bullish": None,
                "tk_cross": "NEUTRAL", "tenkan": 0, "kijun": 0, "span_a": 0, "span_b": 0}

    def donchian_mid(n, offset=0):
        end = len(candles) - offset
        start = end - n
        if start < 0: return candles[-1]["close"]
        window = candles[start:end]
        return (max(c["high"] for c in window) + min(c["low"] for c in window)) / 2

    tenkan  = donchian_mid(9)   # linha de conversão (9 períodos)
    kijun   = donchian_mid(26)  # linha base (26 períodos)
    span_a  = (tenkan + kijun) / 2
    span_b  = donchian_mid(52)

    price   = candles[-1]["close"]
    cloud_top    = max(span_a, span_b)
    cloud_bottom = min(span_a, span_b)

    above_cloud   = price > cloud_top
    below_cloud   = price < cloud_bottom
    cloud_bullish = span_a > span_b   # nuvem verde = bullish

    # TK Cross: Tenkan acima de Kijun = bullish
    tk_cross = ("BULLISH" if tenkan > kijun else
                "BEARISH" if tenkan < kijun else "NEUTRAL")

    # Sinal final
    if above_cloud and cloud_bullish and tk_cross == "BULLISH":
        signal = "STRONG_BUY"
    elif above_cloud and tk_cross == "BULLISH":
        signal = "BUY"
    elif below_cloud and not cloud_bullish and tk_cross == "BEARISH":
        signal = "STRONG_SELL"
    elif below_cloud:
        signal = "SELL"
    else:
        signal = "NEUTRAL"  # preço dentro da nuvem = zona de indecisão

    return {
        "signal":       signal,
        "above_cloud":  above_cloud,
        "below_cloud":  below_cloud,
        "cloud_bullish": cloud_bullish,
        "tk_cross":     tk_cross,
        "tenkan":       round(tenkan, 6),
        "kijun":        round(kijun, 6),
        "span_a":       round(span_a, 6),
        "span_b":       round(span_b, 6),
        "cloud_top":    round(cloud_top, 6),
        "cloud_bottom": round(cloud_bottom, 6),
    }


def calc_cmf(candles: list, period: int = 20) -> dict:
    """
    Chaikin Money Flow — mede pressão de compra/venda via volume.
    CMF > +0.1 = acumulação (smart money comprando)
    CMF < -0.1 = distribuição (smart money vendendo)
    CMF > +0.25 = sinal forte de compra institucional
    """
    if len(candles) < period:
        return {"cmf": 0, "signal": "NEUTRAL"}

    window = candles[-period:]
    mf_vol = 0; total_vol = 0

    for c in window:
        hl = c["high"] - c["low"]
        if hl == 0: continue
        # Money Flow Multiplier: onde fechou dentro do range
        mfm = ((c["close"] - c["low"]) - (c["high"] - c["close"])) / hl
        mf_vol   += mfm * c["volume"]
        total_vol += c["volume"]

    cmf = round(mf_vol / total_vol, 4) if total_vol > 0 else 0

    signal = ("STRONG_BUY"  if cmf >  0.25 else
              "BUY"          if cmf >  0.10 else
              "STRONG_SELL"  if cmf < -0.25 else
              "SELL"         if cmf < -0.10 else
              "NEUTRAL")

    return {"cmf": cmf, "signal": signal}


def calc_cci(candles: list, period: int = 20) -> dict:
    """
    Commodity Channel Index — detecta extremos de preço.
    CCI < -100 = oversold (zona de compra)
    CCI > +100 = overbought (zona de venda)
    Combinado com RSI oversold = sinal muito forte
    """
    if len(candles) < period:
        return {"cci": 0, "signal": "NEUTRAL"}

    window = candles[-period:]
    typical_prices = [(c["high"] + c["low"] + c["close"]) / 3 for c in window]
    sma = sum(typical_prices) / period
    mean_dev = sum(abs(tp - sma) for tp in typical_prices) / period

    if mean_dev == 0:
        return {"cci": 0, "signal": "NEUTRAL"}

    cci = round((typical_prices[-1] - sma) / (0.015 * mean_dev), 2)

    signal = ("STRONG_BUY"  if cci < -200 else
              "BUY"          if cci < -100 else
              "STRONG_SELL"  if cci >  200 else
              "SELL"         if cci >  100 else
              "NEUTRAL")

    return {"cci": cci, "signal": signal}


def calc_hma(closes: list, period: int = 20) -> dict:
    """
    Hull Moving Average — média móvel de baixíssima latência.
    Responde muito mais rápido que EMA sem ruído excessivo.
    Direção (subindo/descendo) é mais importante que o valor.
    """
    if len(closes) < period * 2:
        return {"hma": closes[-1] if closes else 0, "direction": "NEUTRAL"}

    half_period = period // 2
    sqrt_period  = int(period ** 0.5)

    wma_half = calc_ema(closes, half_period)
    wma_full = calc_ema(closes, period)

    # HMA = WMA(2*WMA(n/2) - WMA(n), sqrt(n))
    raw_hma = 2 * wma_half - wma_full

    # Aproximação via EMA sobre os últimos períodos
    if len(closes) >= period + sqrt_period:
        raw_series = [2 * calc_ema(closes[:i], half_period) - calc_ema(closes[:i], period)
                      for i in range(period, len(closes) + 1)]
        hma = calc_ema(raw_series, sqrt_period)
    else:
        hma = raw_hma

    # Direção baseada em comparação com valor anterior
    if len(closes) >= period + sqrt_period + 1:
        raw_series_prev = [2 * calc_ema(closes[:i], half_period) - calc_ema(closes[:i], period)
                           for i in range(period, len(closes))]
        hma_prev = calc_ema(raw_series_prev, sqrt_period) if len(raw_series_prev) >= sqrt_period else hma
    else:
        hma_prev = hma

    direction = ("UP" if hma > hma_prev else "DOWN" if hma < hma_prev else "FLAT")
    price = closes[-1]
    position = ("ABOVE" if price > hma else "BELOW")

    return {"hma": round(hma, 6), "direction": direction, "position": position}


def calc_pivot_points(candles: list) -> dict:
    """
    Pivot Points clássicos — níveis de suporte e resistência dinâmicos.
    Baseados no candle anterior (H, L, C).
    PP = (H + L + C) / 3
    R1 = 2*PP - L | R2 = PP + (H - L) | R3 = H + 2*(PP - L)
    S1 = 2*PP - H | S2 = PP - (H - L) | S3 = L - 2*(H - PP)
    """
    if len(candles) < 2:
        return {"pp": 0, "r1": 0, "r2": 0, "s1": 0, "s2": 0, "zone": "UNKNOWN"}

    prev = candles[-2]
    H, L, C = prev["high"], prev["low"], prev["close"]
    pp = (H + L + C) / 3
    r1 = 2 * pp - L
    r2 = pp + (H - L)
    r3 = H + 2 * (pp - L)
    s1 = 2 * pp - H
    s2 = pp - (H - L)
    s3 = L - 2 * (H - pp)

    price = candles[-1]["close"]
    tolerance = (H - L) * 0.05  # 5% do range como zona de toque

    zone = "UNKNOWN"
    if abs(price - s1) < tolerance: zone = "AT_S1"
    elif abs(price - s2) < tolerance: zone = "AT_S2"
    elif abs(price - r1) < tolerance: zone = "AT_R1"
    elif abs(price - r2) < tolerance: zone = "AT_R2"
    elif abs(price - pp) < tolerance: zone = "AT_PP"
    elif price < s2: zone = "BELOW_S2"
    elif price < s1: zone = "BETWEEN_S1_S2"
    elif price < pp: zone = "BETWEEN_PP_S1"
    elif price < r1: zone = "BETWEEN_PP_R1"
    elif price < r2: zone = "BETWEEN_R1_R2"
    else: zone = "ABOVE_R2"

    return {
        "pp": round(pp, 6), "r1": round(r1, 6), "r2": round(r2, 6), "r3": round(r3, 6),
        "s1": round(s1, 6), "s2": round(s2, 6), "s3": round(s3, 6), "zone": zone,
        "near_support": zone in ("AT_S1", "AT_S2", "BETWEEN_S1_S2"),
        "near_resistance": zone in ("AT_R1", "AT_R2"),
    }


def calc_williams_r(candles: list, period: int = 14) -> dict:
    """
    Williams %R — identifica extremos de momentum.
    Escala de 0 a -100:
    -80 a -100 = oversold (zona de compra)
    0 a -20    = overbought (zona de venda)
    Complementa bem o Stochastic RSI.
    """
    if len(candles) < period:
        return {"wr": -50, "signal": "NEUTRAL"}

    window = candles[-period:]
    highest_high = max(c["high"] for c in window)
    lowest_low   = min(c["low"]  for c in window)
    close = candles[-1]["close"]

    if highest_high == lowest_low:
        return {"wr": -50, "signal": "NEUTRAL"}

    wr = round(((highest_high - close) / (highest_high - lowest_low)) * -100, 2)

    signal = ("STRONG_BUY"  if wr <= -90 else
              "BUY"          if wr <= -80 else
              "STRONG_SELL"  if wr >= -10 else
              "SELL"         if wr >= -20 else
              "NEUTRAL")

    return {"wr": wr, "signal": signal}


# ══════════════════════════════════════════
#  SISTEMA DE VOTAÇÃO (23 indicadores — v8)
# ══════════════════════════════════════════

def voting_system(ind: dict) -> dict:
    votes = {}
    rsi_avg = ind["rsi_1h"] * 0.2 + ind["rsi_4h"] * 0.5 + ind["rsi_1d"] * 0.3
    votes["rsi"]          = 2 if rsi_avg < 30 else 1 if rsi_avg < 45 else -2 if rsi_avg > 70 else -1 if rsi_avg > 60 else 0
    st = ind["supertrend"]
    votes["supertrend"]   = 2 if st["signal"] == "BUY" else 1 if st["is_uptrend"] else -2 if st["signal"] == "SELL" else -1
    votes["psar"]         = 1 if ind["psar"]["is_uptrend"] else -1
    adx = ind["adx"]
    votes["adx"]          = (-2 if adx["trend_strength"] == "WEAK" else -1 if adx["trend_strength"] == "STRONG"
                             else 1 if adx["plus_di"] > adx["minus_di"] else -1)
    macd = ind["macd_4h"]
    votes["macd"]         = 2 if macd["histogram"] > 0 and macd["macd"] > macd["signal"] else -2 if macd["histogram"] < 0 else 0
    bb = ind["bb_4h"]
    votes["bollinger"]    = 1 if bb["percent_b"] < 0.2 else -1 if bb["percent_b"] > 0.8 else 0
    stoch = ind["stoch_rsi"]
    votes["stoch_rsi"]    = 2 if stoch["signal"] == "OVERSOLD" else -2 if stoch["signal"] == "OVERBOUGHT" else 0
    div = ind["rsi_divergence"]
    votes["rsi_div"]      = 3 if div["bullish"] else -3 if div["bearish"] else 0
    votes["obv"]          = 1 if ind["obv"]["trend"] == "RISING" else -1
    votes["cvd"]          = 1 if ind["cvd"]["trend"] == "BULLISH" else -1
    fib = ind["fibonacci"]
    votes["fibonacci"]    = 2 if "SUPPORT" in fib["zone"] else -1 if fib["zone"] == "RESISTANCE" else 0
    votes["volume"]       = 1 if ind["vol_ratio"] > 1.5 else -1 if ind["vol_ratio"] < 0.5 else 0
    fg = ind["fg_value"]
    votes["fear_greed"]   = 2 if fg <= 20 else 1 if fg <= 35 else -2 if fg >= 80 else -1 if fg >= 70 else 0
    fr = ind["funding"]["signal"]
    votes["funding"]      = 1 if fr == "EXTREME_SHORT" else -1 if fr == "EXTREME_LONG" else 0
    ls = ind["long_short"]["signal"]
    votes["long_short"]   = 1 if ls == "EXTREME_SHORT" else -1 if ls == "EXTREME_LONG" else 0
    oi = ind["open_interest"]["trend"]
    votes["open_interest"] = 1 if oi == "INCREASING" and ind.get("change_24h", 0) > 0 else -1 if oi == "INCREASING" and ind.get("change_24h", 0) < 0 else 0
    ns = ind.get("news_sentiment", {}).get("signal", "NEUTRAL")
    votes["news"]         = 1 if ns == "BULLISH" else -1 if ns == "BEARISH" else 0
    # Order Book Imbalance
    ob = ind.get("order_book", {})
    ob_sig = ob.get("signal", "NEUTRAL")
    votes["order_book"]   = 2 if ob_sig == "STRONG_BUY" else 1 if ob_sig == "BUY" else -1 if ob_sig == "SELL" else 0
    # VWAP position
    vwap = ind.get("vwap", {})
    vwap_pos = vwap.get("position", "UNKNOWN")
    votes["vwap"]         = 1 if vwap_pos == "BELOW_VWAP" else -1 if vwap_pos == "ABOVE_VWAP" else 0

    # ── NOVOS v8 ──────────────────────────────
    # Ichimoku Cloud
    ichi = ind.get("ichimoku", {})
    ichi_sig = ichi.get("signal", "NEUTRAL")
    votes["ichimoku"]     = (3 if ichi_sig == "STRONG_BUY"  else
                             2 if ichi_sig == "BUY"         else
                            -2 if ichi_sig == "SELL"        else
                            -3 if ichi_sig == "STRONG_SELL" else 0)

    # CMF — Chaikin Money Flow
    cmf = ind.get("cmf", {})
    cmf_sig = cmf.get("signal", "NEUTRAL")
    votes["cmf"]          = (2 if cmf_sig == "STRONG_BUY"  else
                             1 if cmf_sig == "BUY"         else
                            -1 if cmf_sig == "SELL"        else
                            -2 if cmf_sig == "STRONG_SELL" else 0)

    # CCI — Commodity Channel Index
    cci = ind.get("cci", {})
    cci_sig = cci.get("signal", "NEUTRAL")
    votes["cci"]          = (2 if cci_sig == "STRONG_BUY"  else
                             1 if cci_sig == "BUY"         else
                            -1 if cci_sig == "SELL"        else
                            -2 if cci_sig == "STRONG_SELL" else 0)

    # HMA — Hull Moving Average (direção e posição do preço)
    hma = ind.get("hma", {})
    votes["hma"]          = (2 if hma.get("direction") == "UP"   and hma.get("position") == "ABOVE" else
                              1 if hma.get("direction") == "UP"   else
                             -1 if hma.get("direction") == "DOWN" else 0)

    # Pivot Points — suporte/resistência dinâmicos
    pivots = ind.get("pivots", {})
    votes["pivots"]       = (1 if pivots.get("near_support")    else
                            -1 if pivots.get("near_resistance")  else 0)

    # Williams %R
    wr = ind.get("williams_r", {})
    wr_sig = wr.get("signal", "NEUTRAL")
    votes["williams_r"]   = (2 if wr_sig == "STRONG_BUY"  else
                             1 if wr_sig == "BUY"         else
                            -1 if wr_sig == "SELL"        else
                            -2 if wr_sig == "STRONG_SELL" else 0)

    total = sum(votes.values())
    max_p = sum(abs(v) for v in [2, 2, 1, 2, 2, 1, 2, 3, 1, 1, 2, 1, 2, 1, 1, 1, 1, 2, 1, 3, 2, 2, 2, 1, 2])
    return {"total": total, "max_possible": max_p,
            "normalized": round((total / max_p) * 10, 1) if max_p else 0,
            "votes": votes,
            "bullish_count": sum(1 for v in votes.values() if v > 0),
            "bearish_count": sum(1 for v in votes.values() if v < 0)}


# ══════════════════════════════════════════
#  COLETA COMPLETA DE INDICADORES
# ══════════════════════════════════════════

def get_all_indicators(sym, fg_value):
    c1h = get_klines(sym, "1h", 60)
    c4h = get_klines(sym, "4h", 150)
    c1d = get_klines(sym, "1d", 60)
    if not c4h: return None
    cl1 = [c["close"] for c in c1h] if c1h else []
    cl4 = [c["close"] for c in c4h]
    cl1d = [c["close"] for c in c1d] if c1d else []
    vols = [c["volume"] for c in c4h]
    ticker = get_ticker_24h(sym)
    ch24 = ticker.get("change_24h", 0)
    ch7 = round(((cl1d[-1] - cl1d[-8]) / cl1d[-8]) * 100, 2) if len(cl1d) >= 8 and cl1d[-8] else 0
    ch30 = round(((cl4[-1] - cl4[0]) / cl4[0]) * 100, 2) if cl4[0] else 0
    atr = calc_atr(c4h); atr_pct = round((atr / cl4[-1]) * 100, 2) if cl4[-1] else 0
    ind = {
        "symbol": sym, "price": cl4[-1],
        "rsi_1h": calc_rsi(cl1) if cl1 else 50, "rsi_4h": calc_rsi(cl4),
        "rsi_1d": calc_rsi(cl1d) if cl1d else 50,
        "ema9": calc_ema(cl4, 9), "ema21": calc_ema(cl4, 21), "ema50": calc_ema(cl4, 50),
        "ema200": calc_ema(cl4, 200) if len(cl4) >= 200 else calc_ema(cl4, len(cl4)),
        "macd_4h": calc_macd(cl4), "bb_4h": calc_bollinger(cl4),
        "vol_ratio": calc_volume_ratio(vols), "atr_pct": atr_pct, "var": calc_var(cl4),
        "supertrend": calc_supertrend(c4h), "psar": calc_parabolic_sar(c4h),
        "adx": calc_adx(c4h), "stoch_rsi": calc_stochastic_rsi(cl4),
        "rsi_divergence": detect_rsi_divergence(c4h, cl4),
        "obv": calc_obv(c4h), "cvd": calc_cvd(c4h), "fibonacci": calc_fibonacci(c4h),
        "funding": get_funding_rate(sym), "long_short": get_long_short_ratio(sym),
        "open_interest": get_open_interest(sym),
        "vwap": calc_vwap(c4h),
        "order_book": get_order_book_data(sym),
        # NOVOS v8
        "ichimoku":   calc_ichimoku(c4h),
        "cmf":        calc_cmf(c4h),
        "cci":        calc_cci(c4h),
        "hma":        calc_hma(cl4),
        "pivots":     calc_pivot_points(c4h),
        "williams_r": calc_williams_r(c4h),
        "fg_value": fg_value, "change_24h": ch24, "change_7d": ch7, "change_30d": ch30,
        "ticker": ticker, "vol_anomaly": calc_volume_ratio(vols) > 2.5,
    }
    if CRYPTOPANIC_TOKEN:
        ind["news_sentiment"] = get_news_sentiment(sym)
    ind["voting"] = voting_system(ind)
    return ind


# ══════════════════════════════════════════
#  MÉTRICAS DE PERFORMANCE
# ══════════════════════════════════════════

def calc_sortino_ratio(state: dict, risk_free_rate: float = 0.05) -> float:
    """Sortino Ratio — considera só downside volatility (melhor que Sharpe para crypto)."""
    sells = [t for t in state.get("history", []) if t["action"] == "SELL"]
    if len(sells) < 5: return 0.0
    returns = [t.get("pnl_pct", 0) / 100 for t in sells]
    avg_r = sum(returns) / len(returns)
    daily_rf = risk_free_rate / 365
    downside = [min(r - daily_rf, 0) ** 2 for r in returns]
    downside_std = (sum(downside) / len(downside)) ** 0.5 if downside else 1
    return round((avg_r - daily_rf) / downside_std, 2) if downside_std else 0.0

def calc_sharpe_ratio(state: dict) -> float:
    sells = [t for t in state.get("history", []) if t["action"] == "SELL"]
    if len(sells) < 5: return 0.0
    returns = [t.get("pnl_pct", 0) / 100 for t in sells]
    avg_r = sum(returns) / len(returns)
    std_r = (sum((r - avg_r) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5 if len(returns) > 1 else 1
    return round(avg_r / std_r, 2) if std_r else 0.0

def calc_profit_factor(state: dict) -> float:
    """Profit Factor = lucro bruto / perda bruta. >1.5 bom, >2.0 excelente."""
    sells = [t for t in state.get("history", []) if t["action"] == "SELL"]
    gross_profit = sum(t.get("pnl_usd", 0) for t in sells if t.get("pnl_usd", 0) > 0)
    gross_loss = abs(sum(t.get("pnl_usd", 0) for t in sells if t.get("pnl_usd", 0) < 0))
    return round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

def calc_expectancy(state: dict) -> float:
    """Expectancy = lucro médio esperado por trade."""
    sells = [t for t in state.get("history", []) if t["action"] == "SELL"]
    if not sells: return 0.0
    return round(sum(t.get("pnl_usd", 0) for t in sells) / len(sells), 2)

def kelly_position_size(state: dict) -> float:
    sells = [t for t in state.get("history", []) if t["action"] == "SELL"]
    if len(sells) < 10: return CAPITAL_PER_TRADE
    wins = [t for t in sells if t.get("pnl_pct", 0) > 0]
    losses = [t for t in sells if t.get("pnl_pct", 0) <= 0]
    if not wins or not losses: return CAPITAL_PER_TRADE
    p = len(wins) / len(sells)
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) / 100
    avg_loss = abs(sum(t["pnl_pct"] for t in losses) / len(losses)) / 100
    if avg_loss == 0: return CAPITAL_PER_TRADE
    kelly = (p * (avg_win / avg_loss) - (1 - p)) / (avg_win / avg_loss) * 0.5
    return max(0.02, min(0.20, kelly))


# ══════════════════════════════════════════
#  CLAUDE
# ══════════════════════════════════════════

def claude_call(prompt, max_tokens=300):
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        return r.json()["content"][0]["text"].strip()
    except Exception as e:
        log.error(f"Claude: {e}"); return None

def parse_json(text):
    try:
        c = text.replace("```json", "").replace("```", "").strip()
        return json.loads(c[c.index("{"):c.rindex("}") + 1])
    except: return {}

def claude_analyze(sym, ind, fg, regime, kelly_pct, sharpe, sortino, profit_factor):
    v = ind["voting"]; adx = ind["adx"]; ob = ind.get("order_book", {})
    vwap = ind.get("vwap", {}); div = ind["rsi_divergence"]
    prompt = f"""Analise {sym} para trade. Bot institucional v7.

VOTAÇÃO (19 indicadores): {v['total']}/{v['max_possible']} (norm:{v['normalized']}/10)
Bullish:{v['bullish_count']} | Bearish:{v['bearish_count']}

CONTEXTO: Regime={regime} | F&G={fg['value']}/100 ({fg['regime']})
Sharpe:{sharpe} | Sortino:{sortino} | PF:{profit_factor} | Kelly:{kelly_pct*100:.1f}%

ORDER BOOK: Spread={ob.get('spread_pct',0):.3f}% | Imbalance={ob.get('imbalance',0):.3f} ({ob.get('signal','?')})
VWAP: {vwap.get('position','?')} | Desvio={vwap.get('deviation_pct',0):+.2f}%

TÉCNICO: Ichimoku={ind.get("ichimoku",{}).get("signal","?")} | Supertrend={"UP" if ind["supertrend"]["is_uptrend"] else 'DOWN'} | ADX={adx['adx']:.0f} ({adx['trend_strength']})
RSI 1h/4h/1d={ind['rsi_1h']}/{ind['rsi_4h']}/{ind['rsi_1d']} | StochRSI={ind['stoch_rsi']['k']:.0f} ({ind['stoch_rsi']['signal']})
Div Bullish={'SIM ⚡' if div['bullish'] else 'não'} | VaR={ind['var']*100:.1f}% | ATR={ind['atr_pct']}%
Funding={ind['funding']['rate']}% | L/S={ind['long_short']['long_pct']}% | OI={ind['open_interest']['trend']}

REGRAS: ADX<20=SKIP | EXTREME_GREED=SKIP | Spread>{MAX_SPREAD_PCT}%=SKIP | BEAR+voto<8=SKIP

JSON sem markdown:
{{"score":7,"action":"BUY|HOLD|SKIP","reason":"<60 chars>","risk":"LOW|MEDIUM|HIGH","conviction":"LOW|MEDIUM|HIGH"}}"""
    raw = claude_call(prompt)
    if not raw:
        return {"score": max(1, v["normalized"]), "action": "HOLD", "reason": "Erro Claude", "risk": "MEDIUM", "conviction": "LOW"}
    d = parse_json(raw)
    return d if d else {"score": 5, "action": "HOLD", "reason": "Parse erro", "risk": "MEDIUM", "conviction": "LOW"}


# ══════════════════════════════════════════
#  ESTADO
# ══════════════════════════════════════════

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
        print(Fore.YELLOW + f"  ↺ Estado carregado — saldo: ${s['balance']:.2f}")
        return s
    except FileNotFoundError:
        return {"balance": PAPER_BALANCE, "positions": {}, "history": [],
                "total_pnl": 0.0, "wins": 0, "losses": 0, "consec_losses": 0,
                "peak_balance": PAPER_BALANCE, "circuit_breaker": False,
                "daily_loss": 0.0, "weekly_loss": 0.0,
                "daily_reset": datetime.now().strftime("%Y-%m-%d"),
                "weekly_reset": datetime.now().strftime("%Y-%W"),
                "last_optimize": None, "last_research": None,
                "grid_orders": {}}

def save_state(state):
    state["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════
#  CIRCUIT BREAKERS
# ══════════════════════════════════════════

def check_circuit_breakers(state):
    today = datetime.now().strftime("%Y-%m-%d"); week = datetime.now().strftime("%Y-%W")
    if state.get("daily_reset") != today: state["daily_loss"] = 0.0; state["daily_reset"] = today
    if state.get("weekly_reset") != week: state["weekly_loss"] = 0.0; state["weekly_reset"] = week
    portfolio = state["balance"]
    for sym, pos in state["positions"].items():
        p = get_price(sym) or pos["entry_price"]; portfolio += pos["qty"] * p
    if portfolio > state.get("peak_balance", PAPER_BALANCE):
        state["peak_balance"] = portfolio
    peak = state.get("peak_balance", PAPER_BALANCE)
    drawdown = (peak - portfolio) / peak if peak else 0
    if drawdown >= MAX_DRAWDOWN_PCT:
        if not state.get("circuit_breaker"):
            state["circuit_breaker"] = True
            msg = f"Drawdown: {drawdown*100:.1f}%"
            print(Fore.RED + f"\n  🔴 CIRCUIT BREAKER GLOBAL — {msg}")
            tg_alert("🔴 CIRCUIT BREAKER GLOBAL", msg, urgent=True)
            save_state(state)
        return True
    dl = abs(state.get("daily_loss", 0)) / PAPER_BALANCE
    if dl >= MAX_DAILY_LOSS_PCT:
        print(Fore.RED + f"  🔴 CB DIÁRIO — {dl*100:.1f}%")
        tg_alert("CB DIÁRIO", f"Perda: {dl*100:.1f}%", urgent=True)
        return True
    wl = abs(state.get("weekly_loss", 0)) / PAPER_BALANCE
    if wl >= MAX_WEEKLY_LOSS_PCT:
        print(Fore.RED + f"  🔴 CB SEMANAL — {wl*100:.1f}%")
        return True
    if state.get("consec_losses", 0) >= MAX_CONSEC_LOSSES:
        print(Fore.RED + f"  🔴 {MAX_CONSEC_LOSSES} PERDAS CONSECUTIVAS — Pausando.")
        state["consec_losses"] = 0; return True
    if state.get("circuit_breaker"):
        print(Fore.RED + "\n  🔴 CB ATIVO. Edite circuit_breaker=false no JSON."); return True
    return False

def check_correlation_guard(state, symbol):
    sym_group = next((g for g, syms in CORRELATION_GROUPS.items() if symbol in syms), None)
    if not sym_group: return True
    count = sum(1 for s in state["positions"] if s in CORRELATION_GROUPS.get(sym_group, []))
    if count >= MAX_CORRELATED:
        print(Fore.YELLOW + f"    ⚠ Correlation guard: {count} pos em {sym_group}. Pulando {symbol}.")
        return False
    return True


# ══════════════════════════════════════════
#  SLIPPAGE REALISTA
# ══════════════════════════════════════════

def apply_slippage(sym, price, side="buy"):
    """Aplica slippage realista no paper trading."""
    slippage = SLIPPAGE_LIQUID if sym in LIQUID_PAIRS else SLIPPAGE_NORMAL
    return price * (1 + slippage) if side == "buy" else price * (1 - slippage)


# ══════════════════════════════════════════
#  ORDENS
# ══════════════════════════════════════════

def execute_buy(sym, amount, price, mode):
    qty = amount / price
    if mode == "live":
        r = b_signed("POST", "/api/v3/order", {"symbol": f"{sym}USDT", "side": "BUY",
                                                "type": "MARKET", "quoteOrderQty": round(amount, 2)})
        if r:
            fills = r.get("fills", [{}])
            return {"qty": float(r.get("executedQty", qty)), "price": float(fills[0].get("price", price))}
        return None
    # Paper trading com slippage realista
    exec_price = apply_slippage(sym, price, "buy")
    return {"qty": amount / exec_price, "price": exec_price}

def execute_sell(sym, qty, price, mode):
    if mode == "live":
        r = b_signed("POST", "/api/v3/order", {"symbol": f"{sym}USDT", "side": "SELL",
                                                "type": "MARKET", "quantity": round(qty, 6)})
        if r:
            fills = r.get("fills", [{}])
            return {"price": float(fills[0].get("price", price))}
        return None
    exec_price = apply_slippage(sym, price, "sell")
    return {"price": exec_price}


# ══════════════════════════════════════════
#  GRID TRADING (regime SIDEWAYS)
# ══════════════════════════════════════════

def run_grid_cycle(state, mode, sym, current_price, atr_pct):
    """
    Grid adaptativo: cria ordens de compra abaixo e venda acima do preço atual.
    Espaçamento dinâmico baseado no ATR.
    """
    grid = state.get("grid_orders", {})

    # Espaçamento adaptativo baseado no ATR
    spacing = max(GRID_SPACING_PCT, atr_pct / 100 * 0.5)
    amount_per_level = state["balance"] * GRID_AMOUNT_PCT

    if sym not in grid:
        grid[sym] = {"levels": [], "base_price": current_price, "spacing": spacing}
        # Cria níveis do grid
        for i in range(1, GRID_LEVELS + 1):
            buy_price = current_price * (1 - spacing * i)
            sell_price = current_price * (1 + spacing * i)
            grid[sym]["levels"].append({
                "buy_price": round(buy_price, 6),
                "sell_price": round(sell_price, 6),
                "level": i,
                "filled": False,
                "qty": 0
            })
        state["grid_orders"] = grid
        print(Fore.CYAN + f"  📊 GRID {sym}: {GRID_LEVELS} níveis | Espaçamento: {spacing*100:.1f}% (ATR-based)")
        tg(f"📊 <b>GRID {sym}</b>\n{GRID_LEVELS} níveis | Espaçamento: {spacing*100:.1f}%\nPreço base: ${current_price:.4f}", silent=True)
        return

    # Verifica execução de níveis existentes
    levels = grid[sym]["levels"]
    for lvl in levels:
        # Nível de compra atingido
        if not lvl["filled"] and current_price <= lvl["buy_price"] and state["balance"] >= amount_per_level:
            r = execute_buy(sym, amount_per_level, current_price, mode)
            if r:
                state["balance"] -= amount_per_level
                lvl["filled"] = True
                lvl["qty"] = r["qty"]
                lvl["fill_price"] = r["price"]
                profit_target = r["price"] * (1 + spacing)
                print(Fore.GREEN + f"  [GRID BUY] {sym} Nível {lvl['level']} @ ${r['price']:.4f} | TP: ${profit_target:.4f}")
                tg_trade("GRID BUY", sym, r["price"], amount_per_level, f"Grid nível {lvl['level']}")
                save_state(state)

        # Nível de venda (realizando lucro do grid)
        elif lvl["filled"] and lvl.get("qty", 0) > 0 and current_price >= lvl.get("fill_price", 0) * (1 + spacing):
            r = execute_sell(sym, lvl["qty"], current_price, mode)
            if r:
                proceeds = lvl["qty"] * r["price"]
                cost = lvl["qty"] * lvl["fill_price"]
                pnl = proceeds - cost
                state["balance"] += proceeds
                state["total_pnl"] += pnl
                pnl_pct = (pnl / cost) * 100
                lvl["filled"] = False; lvl["qty"] = 0
                print(Fore.GREEN + f"  [GRID SELL] {sym} Nível {lvl['level']} @ ${r['price']:.4f} | P&L: {pnl_pct:+.1f}%")
                tg_trade("GRID SELL", sym, r["price"], proceeds, f"Grid nível {lvl['level']}", pnl_pct)
                save_state(state)

    # Remove grid se regime mudar
    if sym in grid:
        state["grid_orders"] = grid

def clear_grid(state, sym):
    """Remove grid de um símbolo."""
    if sym in state.get("grid_orders", {}):
        del state["grid_orders"][sym]
        print(Fore.YELLOW + f"  Grid {sym} removido (regime mudou).")


# ══════════════════════════════════════════
#  GESTÃO DE POSIÇÕES (com Partial TP)
# ══════════════════════════════════════════

def check_exits(state, mode):
    if not state["positions"]: return
    print(Fore.WHITE + f"\n  🔍 Verificando {len(state['positions'])} posição(ões)...")
    for sym in list(state["positions"].keys()):
        pos = state["positions"].get(sym)
        if not pos: continue
        price = get_price(sym)
        if not price: continue
        entry = pos["entry_price"]; pnl = ((price - entry) / entry) * 100

        # Time-based exit
        entry_time = datetime.strptime(pos["entry_time"], "%Y-%m-%d %H:%M")
        hours_open = (datetime.now() - entry_time).total_seconds() / 3600
        if hours_open > TIME_EXIT_HOURS and abs(pnl) < 2:
            _close_position(state, sym, price, f"Time exit ({hours_open:.0f}h)", mode)
            continue

        # Trailing stop via SAR
        c4h = get_klines(sym, "4h", 50)
        if c4h:
            psar = calc_parabolic_sar(c4h)
            if psar["is_uptrend"] and psar["sar"] > pos["stop_loss"]:
                pos["stop_loss"] = round(psar["sar"], 8)
        if pos.get("at_breakeven") and pnl >= TP1_PCT * 100:
            new_sl = price * (1 - TRAILING_STOP_PCT)
            if new_sl > pos["stop_loss"]: pos["stop_loss"] = round(new_sl, 8)

        # DCA automático
        dca = pos.get("dca_count", 0)
        if pnl <= -(DCA_TRIGGER_PCT * 100) * (dca + 1) and dca < DCA_MAX_TIMES and not pos.get("at_breakeven"):
            dca_amt = pos["amount_usd"] * 0.5
            if state["balance"] >= dca_amt and dca_amt >= 5:
                r = execute_buy(sym, dca_amt, price, mode)
                if r:
                    tc = pos["amount_usd"] + dca_amt; tq = pos["qty"] + r["qty"]; avg = tc / tq
                    state["balance"] -= dca_amt
                    pos.update({"entry_price": round(avg, 8), "amount_usd": tc, "qty": tq,
                                "stop_loss": round(avg * (1 - STOP_LOSS_PCT), 8),
                                "tp1": round(avg * (1 + TP1_PCT), 8),
                                "tp2": round(avg * (1 + TP2_PCT), 8),
                                "tp3": round(avg * (1 + TP3_PCT), 8), "dca_count": dca + 1})
                    print(Fore.YELLOW + f"    {sym}: DCA #{dca+1} @ ${price:.4f} | Avg: ${avg:.4f}")
                    save_state(state)

        # Partial TP1
        if not pos.get("tp1_done") and price >= pos.get("tp1", entry * (1 + TP1_PCT)):
            close_qty = pos["qty"] * 0.5
            r = execute_sell(sym, close_qty, price, mode)
            if r:
                proceeds = close_qty * r["price"]; pnl_usd = proceeds - (pos["amount_usd"] * 0.5)
                state["balance"] += proceeds; state["total_pnl"] += pnl_usd
                pos["qty"] -= close_qty; pos["amount_usd"] -= pos["amount_usd"] * 0.5
                pos["tp1_done"] = True; pos["at_breakeven"] = True
                pos["stop_loss"] = round(pos["entry_price"], 8)
                state["wins"] += 1; state["consec_losses"] = 0
                pnl_pct_tp1 = ((r["price"] - entry) / entry) * 100
                print(Fore.GREEN + f"\n  [TP1 50%] {sym} @ ${r['price']:.4f} | P&L:{pnl_pct_tp1:+.1f}% | SL→breakeven")
                tg_trade("TP1 PARCIAL 50%", sym, r["price"], proceeds, "TP1 atingido", pnl_pct_tp1)
                state["history"].append({"time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "symbol": sym, "action": "SELL", "price": r["price"],
                    "pnl_usd": pnl_usd, "pnl_pct": pnl_pct_tp1, "reason": "TP1 parcial 50%"})
                save_state(state)
            continue

        # Partial TP2
        if pos.get("tp1_done") and not pos.get("tp2_done") and price >= pos.get("tp2", entry * (1 + TP2_PCT)):
            close_qty = pos["qty"] * 0.6
            r = execute_sell(sym, close_qty, price, mode)
            if r:
                proceeds = close_qty * r["price"]; pnl_usd = proceeds - (pos["amount_usd"] * 0.6)
                state["balance"] += proceeds; state["total_pnl"] += pnl_usd
                pos["qty"] -= close_qty; pos["amount_usd"] -= pos["amount_usd"] * 0.6
                pos["tp2_done"] = True
                pnl_pct_tp2 = ((r["price"] - entry) / entry) * 100
                print(Fore.GREEN + f"\n  [TP2 60%] {sym} @ ${r['price']:.4f} | P&L:{pnl_pct_tp2:+.1f}%")
                tg_trade("TP2 PARCIAL 60%", sym, r["price"], proceeds, "TP2 atingido", pnl_pct_tp2)
                save_state(state)
            continue

        # Stop ou TP3 final
        reason = None
        if price <= pos["stop_loss"]: reason = f"Stop loss ({pnl:.1f}%)"
        elif price >= pos.get("tp3", entry * (1 + TP3_PCT)): reason = f"TP3 final ({pnl:.1f}%)"
        if reason:
            _close_position(state, sym, price, reason, mode)
        else:
            t1 = "✓" if pos.get("tp1_done") else "·"
            t2 = "✓" if pos.get("tp2_done") else "·"
            be = "BE" if pos.get("at_breakeven") else ""
            c = Fore.GREEN if pnl >= 0 else Fore.RED
            print(c + f"    {sym}: ${price:.4f} | {pnl:+.1f}% | SL:${pos['stop_loss']:.4f} | TP1:{t1} TP2:{t2} {be} | {hours_open:.0f}h")

def _close_position(state, sym, price, reason, mode):
    pos = state["positions"].get(sym)
    if not pos: return
    r = execute_sell(sym, pos["qty"], price, mode)
    if not r: return
    proceeds = pos["qty"] * r["price"]; pnl_usd = proceeds - pos["amount_usd"]
    pnl_pct = (pnl_usd / pos["amount_usd"]) * 100 if pos["amount_usd"] else 0
    state["balance"] += proceeds; state["total_pnl"] += pnl_usd
    state["daily_loss"] += min(pnl_usd, 0); state["weekly_loss"] += min(pnl_usd, 0)
    if pnl_usd >= 0:
        state["wins"] += 1; state["consec_losses"] = 0
    else:
        state["losses"] += 1; state["consec_losses"] = state.get("consec_losses", 0) + 1
    del state["positions"][sym]
    c = Fore.GREEN if pnl_usd >= 0 else Fore.RED
    print(c + f"\n  [SELL] {sym} @ ${r['price']:.4f} | {pnl_pct:+.1f}% (${pnl_usd:+.2f})\n    → {reason}")
    tg_trade("SELL", sym, r["price"], proceeds, reason, pnl_pct)
    state["history"].append({"time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "symbol": sym, "action": "SELL", "price": r["price"],
        "pnl_usd": pnl_usd, "pnl_pct": pnl_pct, "reason": reason})
    save_state(state)


# ══════════════════════════════════════════
#  AUTO-OTIMIZAÇÃO E AUTO-PESQUISA
# ══════════════════════════════════════════

def auto_optimize(state):
    sells = [t for t in state.get("history", []) if t["action"] == "SELL"]
    if len(sells) < 5:
        print(Fore.YELLOW + "  ⚙ Auto-otimização: mín. 5 trades"); return
    wins = [t for t in sells if t.get("pnl_usd", 0) >= 0]
    losses = [t for t in sells if t.get("pnl_usd", 0) < 0]
    wr = len(wins) / len(sells) * 100
    avg_w = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
    avg_l = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0
    sharpe = calc_sharpe_ratio(state); sortino = calc_sortino_ratio(state)
    pf = calc_profit_factor(state); exp = calc_expectancy(state)
    kelly = kelly_position_size(state)
    print(Fore.CYAN + f"\n  ⚙ OTIMIZAÇÃO — {len(sells)} trades | WR:{wr:.0f}% | Sharpe:{sharpe} | Sortino:{sortino} | PF:{pf}")
    prompt = f"""Bot de trading crypto nível institucional. Analise e sugira ajustes:
{len(sells)} trades, WR={wr:.1f}%, AvgWin={avg_w:.1f}%, AvgLoss={avg_l:.1f}%
Sharpe={sharpe}, Sortino={sortino}, PF={pf}, Expectancy=${exp:.2f}, Kelly={kelly*100:.1f}%
PnL=${state['total_pnl']:+.2f}

JSON:
{{"resumo":"1 frase","sugestoes":["s1","s2","s3"],"tp1":"manter|aumentar|diminuir","tp2":"manter|aumentar|diminuir","min_vote":"manter|aumentar|diminuir"}}"""
    raw = claude_call(prompt, 400)
    if raw:
        d = parse_json(raw)
        if d:
            print(f"    📊 {d.get('resumo', '')}")
            for s in d.get("sugestoes", []): print(f"    → {s}")
            d["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            d["metrics"] = {"sharpe": sharpe, "sortino": sortino, "profit_factor": pf,
                            "expectancy": exp, "kelly": kelly, "winrate": wr}
            with open(OPTIMIZE_FILE, "w", encoding="utf-8") as f: json.dump(d, f, indent=2)
            tg(f"⚙️ <b>AUTO-OTIMIZAÇÃO</b>\n{d.get('resumo', '')}\nSharpe:{sharpe} | Sortino:{sortino} | PF:{pf}", silent=True)
    state["last_optimize"] = datetime.now().strftime("%Y-%m-%d")

def auto_research():
    print(Fore.CYAN + "\n  🔍 AUTO-PESQUISA — Buscando melhorias...")
    prompt = """Bot de trading crypto institucional v7. Já implementado:
Order Book Imbalance, Bid/Ask Spread filter, VWAP âncora, Telegram alerts, Grid Trading adaptativo,
Slippage realista paper trading, Sortino Ratio, Profit Factor, Expectancy, Kelly Criterion,
Sharpe Ratio, Partial TP (TP1/TP2/TP3), Stop Loss Breakeven, Correlation Guard,
Consecutive Loss CB, Time-Based Exit, VaR, 19 indicadores com votação, RSI Divergência,
Supertrend, Parabolic SAR, ADX, StochRSI, OBV, CVD, Fibonacci, Fear&Greed,
Funding Rate, OI, L/S Ratio, CryptoPanic news, DCA automático, multi-TF 1h+4h+1d,
circuit breakers global/diário/semanal, auto-otimização Claude, regime detection.

Quais são as 5 próximas melhorias de MAIOR IMPACTO não implementadas ainda?
Foque em melhorias PRÁTICAS com APIs gratuitas ou sem API.

JSON:
{"melhorias":[{"titulo":"nome","descricao":"o que faz","impacto":"ALTO|MEDIO","api":"none ou nome","dificuldade":"FACIL|MEDIO|DIFICIL"}],"tendencias":"2026","prioridade":"qual fazer primeiro"}"""
    raw = claude_call(prompt, 800)
    if raw:
        d = parse_json(raw)
        if d:
            d["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            with open(RESEARCH_FILE, "w", encoding="utf-8") as f: json.dump(d, f, indent=2, ensure_ascii=False)
            print(Fore.GREEN + f"  ✅ Pesquisa salva em {RESEARCH_FILE}")
            print(f"  📈 {d.get('tendencias', '')}")
            print(f"  🎯 {d.get('prioridade', '')}")
            for m in d.get("melhorias", []):
                print(f"  {m['titulo']:<28} {m['impacto']:<8} {m['dificuldade']}")
            tg(f"🔍 <b>AUTO-PESQUISA</b>\n{d.get('tendencias','')}\n🎯 {d.get('prioridade','')}", silent=True)
            return d
    return None


# ══════════════════════════════════════════
#  CICLO PRINCIPAL
# ══════════════════════════════════════════

def run_cycle(state, mode):
    if check_circuit_breakers(state): return

    lo = state.get("last_optimize")
    if not lo or (datetime.now() - datetime.strptime(lo, "%Y-%m-%d")).days >= OPTIMIZE_DAYS:
        auto_optimize(state); save_state(state)

    lr = state.get("last_research")
    if not lr or (datetime.now() - datetime.strptime(lr, "%Y-%m-%d")).days >= RESEARCH_DAYS:
        auto_research(); state["last_research"] = datetime.now().strftime("%Y-%m-%d"); save_state(state)

    # Atualiza scores dos ativos com base em histórico
    update_asset_score(state)

    fg = get_fear_greed()
    btc_c = get_klines("BTC", "4h", 60); regime = detect_market_regime(btc_c)
    btc_24h = get_ticker_24h("BTC")
    kelly_pct = kelly_position_size(state)
    sharpe = calc_sharpe_ratio(state); sortino = calc_sortino_ratio(state)
    profit_factor = calc_profit_factor(state); expectancy = calc_expectancy(state)

    print(Fore.CYAN + f"\n{'─'*68}")
    print(Fore.CYAN + f"  📊 TRADING BOT v9 — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(Fore.CYAN + f"{'─'*68}")
    fg_c = Fore.GREEN if fg["value"] <= 30 else Fore.RED if fg["value"] >= 75 else Fore.YELLOW
    rc = Fore.GREEN if regime == "BULL" else Fore.RED if regime == "BEAR" else Fore.YELLOW
    print(fg_c + f"  F&G: {fg['value']}/100 — {fg['label']}")
    print(rc + f"  Regime: {regime} | BTC 24h: {btc_24h.get('change_24h',0):+.2f}%")
    dl = abs(state.get("daily_loss", 0)) / PAPER_BALANCE * 100
    print(f"  Kelly:{kelly_pct*100:.1f}% | Sharpe:{sharpe} | Sortino:{sortino} | PF:{profit_factor} | Exp:${expectancy:.2f}")
    print(f"  Perda dia:{dl:.1f}% | Perdas cons:{state.get('consec_losses',0)}")

    # Scanner de arbitragem triangular
    if ARB_ENABLED:
        arb_opportunities = scan_triangular_arbitrage()
        print_arb_results(arb_opportunities)

    if fg["regime"] == "EXTREME_GREED":
        print(Fore.RED + "  ⚠ EXTREME GREED — Sem compras.")
        check_exits(state, mode)
        print_status(state)
        return

    check_exits(state, mode)

    # Watchlist dinâmica — ordena por score histórico
    active_watchlist = get_dynamic_watchlist(WATCHLIST)

    # Grid Trading em SIDEWAYS
    if regime == "SIDEWAYS":
        print(Fore.CYAN + f"\n  📊 REGIME SIDEWAYS — Ativando Grid Trading")
        for sym in active_watchlist[:5]:
            price = get_price(sym)
            if price:
                c4h = get_klines(sym, "4h", 20)
                atr = calc_atr(c4h) if c4h else 0
                atr_pct = (atr / price) * 100 if price else 2.0
                run_grid_cycle(state, mode, sym, price, atr_pct)
    else:
        for sym in list(state.get("grid_orders", {}).keys()):
            clear_grid(state, sym)

    print(f"\n  {'SYM':<7}{'VOTO':>6}{'AI':>4} {'AÇÃO':<6}{'SPR':>6}{'OBI':>6}{'VWAP':>6}{'DIV':>4} RAZÃO")
    print(f"  {'─'*70}")

    for sym in active_watchlist:
        if sym in state["positions"]:
            print(Fore.YELLOW + f"  {sym:<7}{'—':>6}{'—':>4} {'HOLD':<6}{'—':>6}{'—':>6}{'—':>6}{'—':>4} Posição aberta")
            continue
        if len(state["positions"]) >= MAX_POSITIONS: break
        if not check_correlation_guard(state, sym): continue

        ind = get_all_indicators(sym, fg["value"])
        if not ind: continue

        v = ind["voting"]; vt = v["total"]; adx = ind["adx"]
        ob = ind.get("order_book", {}); vwap_pos = ind.get("vwap", {}).get("position", "?")
        div = "⚡" if ind["rsi_divergence"]["bullish"] else "—"
        spr = f"{ob.get('spread_pct',0):.2f}%"
        obi = f"{ob.get('imbalance',0):+.2f}"
        vwp = vwap_pos[:4]

        # Filtro de spread — bloqueia ativos ilíquidos
        if ob.get("spread_pct", 0) > MAX_SPREAD_PCT:
            print(Fore.WHITE + f"  {sym:<7}{vt:>5}/22{'—':>4} {'SKIP':<6}{spr:>6}{obi:>6}{vwp:>6}{div:>4} Spread alto ({spr})")
            time.sleep(0.1); continue

        if adx["trend_strength"] == "WEAK" and vt < 8:
            print(Fore.WHITE + f"  {sym:<7}{vt:>5}/22{'—':>4} {'SKIP':<6}{spr:>6}{obi:>6}{vwp:>6}{div:>4} ADX fraco")
            time.sleep(0.1); continue

        if regime == "BEAR" and vt < 8:
            print(Fore.RED + f"  {sym:<7}{vt:>5}/22{'—':>4} {'SKIP':<6}{spr:>6}{obi:>6}{vwp:>6}{div:>4} Bear market")
            continue

        if vt < MIN_VOTE_SCORE:
            print(Fore.WHITE + f"  {sym:<7}{vt:>5}/22{'—':>4} {'SKIP':<6}{spr:>6}{obi:>6}{vwp:>6}{div:>4} Votos insuf.")
            time.sleep(0.1); continue

        an = claude_analyze(sym, ind, fg, regime, kelly_pct, sharpe, sortino, profit_factor)
        score = an.get("score", 0); action = an.get("action", "HOLD")
        risk = an.get("risk", "MEDIUM"); conv = an.get("conviction", "MEDIUM")
        reason = an.get("reason", "")[:35]
        color = Fore.GREEN if action == "BUY" and score >= MIN_SCORE else Fore.YELLOW if action == "HOLD" else Fore.WHITE
        print(color + f"  {sym:<7}{vt:>5}/22{score:>3}/10 {action:<6}{spr:>6}{obi:>6}{vwp:>6}{div:>4} {reason}")

        if action == "BUY" and score >= MIN_SCORE and sym not in state["positions"]:
            price = get_price(sym)
            if not price: continue
            rm = {"LOW": 1.2, "MEDIUM": 1.0, "HIGH": 0.7}.get(risk, 1.0)
            cm = {"HIGH": 1.2, "MEDIUM": 1.0, "LOW": 0.8}.get(conv, 1.0)
            div_mult = 1.3 if ind["rsi_divergence"]["bullish"] else 1.0
            ob_mult = 1.2 if ob.get("signal") == "STRONG_BUY" else 1.0
            vol_adj = max(0.5, 1 - (ind["atr_pct"] / MAX_ATR_PCT) * 0.5) if ind["atr_pct"] > MAX_ATR_PCT else 1.0
            var_adj = max(0.6, 1 - max(0, ind["var"] - 0.05) * 5)
            amt = min(state["balance"] * kelly_pct * rm * cm * div_mult * ob_mult * vol_adj * var_adj,
                      state["balance"] * 0.20)
            if amt < 5: print(Fore.YELLOW + f"    ⚠ Saldo insuf. para {sym}"); continue

            r = execute_buy(sym, amt, price, mode)
            if not r: continue
            state["balance"] -= amt

            # Stop loss dinâmico via VaR + SAR
            var_sl = r["price"] * (1 - ind["var"])
            psar_sl = ind["psar"]["sar"] if ind["psar"]["is_uptrend"] else r["price"] * (1 - STOP_LOSS_PCT)
            sl = max(var_sl, psar_sl, r["price"] * (1 - STOP_LOSS_PCT))

            state["positions"][sym] = {
                "entry_price": r["price"], "amount_usd": amt, "qty": r["qty"],
                "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "stop_loss": round(sl, 8),
                "tp1": round(r["price"] * (1 + TP1_PCT), 8),
                "tp2": round(r["price"] * (1 + TP2_PCT), 8),
                "tp3": round(r["price"] * (1 + TP3_PCT), 8),
                "tp1_done": False, "tp2_done": False, "at_breakeven": False,
                "risk": risk, "conviction": conv, "regime_entry": regime,
                "fg_entry": fg["value"], "kelly_used": round(kelly_pct, 3),
                "var_entry": round(ind["var"], 3), "dca_count": 0,
                "vote_score": vt, "claude_score": score,
                "rsi_div_entry": ind["rsi_divergence"]["bullish"],
                "ob_imbalance_entry": ob.get("imbalance", 0),
                "spread_entry": ob.get("spread_pct", 0),
                "vwap_entry": ind.get("vwap", {}).get("position", "?"),
            }
            div_tag = " [⚡DIV]" if ind["rsi_divergence"]["bullish"] else ""
            ob_tag = " [🟢OB]" if ob.get("signal") == "STRONG_BUY" else ""
            print(Fore.GREEN + f"\n  [BUY]{div_tag}{ob_tag} {sym} @ ${r['price']:.4f} | ${amt:.2f}")
            print(f"    SL:${sl:.4f} | TP1:${r['price']*(1+TP1_PCT):.4f} | TP2:${r['price']*(1+TP2_PCT):.4f} | TP3:${r['price']*(1+TP3_PCT):.4f}")
            print(f"    OB:{obi} ({ob.get('signal','?')}) | VWAP:{vwp} | Spread:{spr} | Kelly:{kelly_pct*100:.1f}%")
            tg_trade("BUY", sym, r["price"], amt,
                     f"{reason} | OB:{obi} | VWAP:{vwp}")
            state["history"].append({"time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "symbol": sym, "action": "BUY", "price": r["price"], "amount": amt,
                "reason": an.get("reason", ""), "fg": fg["value"], "regime": regime,
                "vote_score": vt, "rsi_divergence": ind["rsi_divergence"]["bullish"],
                "kelly": round(kelly_pct, 3), "var": round(ind["var"], 3),
                "ob_imbalance": ob.get("imbalance", 0), "spread": ob.get("spread_pct", 0)})
            save_state(state)
        time.sleep(0.3)

    print_status(state)
    save_state(state)

    # Status no Telegram a cada ciclo (silencioso)
    portfolio = state["balance"]
    for sym, pos in state["positions"].items():
        p = get_price(sym) or pos["entry_price"]; portfolio += pos["qty"] * p
    pnl_pct = ((portfolio - PAPER_BALANCE) / PAPER_BALANCE) * 100
    tt = state["wins"] + state["losses"]; wr = (state["wins"] / tt * 100) if tt else 0
    tg_status(state, portfolio, pnl_pct, sharpe, sortino, profit_factor, wr)


def print_status(state):
    portfolio = state["balance"]
    for sym, pos in state["positions"].items():
        p = get_price(sym) or pos["entry_price"]; portfolio += pos["qty"] * p
    pnl_pct = ((portfolio - PAPER_BALANCE) / PAPER_BALANCE) * 100
    tt = state["wins"] + state["losses"]; wr = (state["wins"] / tt * 100) if tt else 0
    peak = state.get("peak_balance", PAPER_BALANCE); dd = ((peak - portfolio) / peak * 100) if peak else 0
    sharpe = calc_sharpe_ratio(state); sortino = calc_sortino_ratio(state)
    pf = calc_profit_factor(state); exp = calc_expectancy(state)
    kelly = kelly_position_size(state)
    c = Fore.GREEN if pnl_pct >= 0 else Fore.RED
    print(Fore.CYAN + f"\n{'═'*68}\n  💼 STATUS DO PORTFÓLIO v9\n{'═'*68}")
    print(f"  Saldo livre:     ${state['balance']:>10,.2f}")
    print(f"  Valor total:     ${portfolio:>10,.2f}")
    print(c + f"  P&L total:       {pnl_pct:>+9.2f}%  (${state['total_pnl']:+,.2f})")
    print(f"  Drawdown:        {dd:>9.2f}%  (limite:{MAX_DRAWDOWN_PCT*100:.0f}%)")
    print(f"  Sharpe:    {sharpe:>7.2f}  | Sortino: {sortino:>7.2f}  (meta:>1.5)")
    print(f"  PF:        {pf:>7.2f}  | Exp/trade: ${exp:>6.2f}")
    print(f"  Kelly:     {kelly*100:>6.1f}%  | WR: {wr:>6.1f}% | Trades: {tt}")
    print(f"  Posições:  {len(state['positions']):>8}  | Grids: {len(state.get('grid_orders', {}))}")
    if state["positions"]:
        print(f"\n  {'SYM':<7}{'ENTRADA':>10}{'ATUAL':>10}{'P&L':>8}{'TP1':>4}{'TP2':>4}{'BE':>4}{'SPR':>7}")
        for sym, pos in state["positions"].items():
            cur = get_price(sym) or pos["entry_price"]
            pnl = ((cur - pos["entry_price"]) / pos["entry_price"]) * 100
            cv = Fore.GREEN if pnl >= 0 else Fore.RED
            t1 = "✓" if pos.get("tp1_done") else "·"
            t2 = "✓" if pos.get("tp2_done") else "·"
            be = "✓" if pos.get("at_breakeven") else "·"
            spr = f"{pos.get('spread_entry', 0):.2f}%"
            print(cv + f"  {sym:<7}${pos['entry_price']:>9.4f}${cur:>9.4f}{pnl:>+7.1f}%{t1:>4}{t2:>4}{be:>4}{spr:>7}")
    print()


# ══════════════════════════════════════════
#  WALK-FORWARD BACKTESTING
# ══════════════════════════════════════════

def run_backtest(days=90):
    print(Fore.CYAN + f"\n╔══════════════════════════════════════════╗")
    print(Fore.CYAN + f"║  WALK-FORWARD BACKTESTING v7 — {days}d   ║")
    print(Fore.CYAN + f"╚══════════════════════════════════════════╝")
    print(f"  Split: 70% treino | 15% validação | 15% teste")
    print(f"  Slippage: {SLIPPAGE_LIQUID*100:.1f}% (líquidos) | {SLIPPAGE_NORMAL*100:.1f}% (outros)")
    print(f"  Fees: 0.1% por operação\n")

    symbols = WATCHLIST[:5]; all_results = []

    for sym in symbols:
        print(f"  Testando {sym}...")
        candles = []; end_ms = int(time.time() * 1000)
        start_ms = end_ms - days * 86400 * 1000; cur = start_ms
        while cur < end_ms:
            data = b_get("/api/v3/klines", {"symbol": f"{sym}USDT", "interval": "1d",
                                            "startTime": cur, "limit": 500})
            if not data: break
            for c in data:
                candles.append({"open": float(c[1]), "high": float(c[2]), "low": float(c[3]),
                                 "close": float(c[4]), "volume": float(c[5])})
            cur = data[-1][0] + 86400000; time.sleep(0.2)
        if len(candles) < 60:
            print(f"  ⚠ Dados insuficientes para {sym}"); continue

        n = len(candles)
        train_end = int(n * 0.70)
        val_end   = int(n * 0.85)
        splits = [("TREINO", candles[:train_end]),
                  ("VALID.", candles[train_end:val_end]),
                  ("TESTE",  candles[val_end:])]

        sym_results = []
        for split_name, split_candles in splits:
            if len(split_candles) < 30: continue
            balance = PAPER_BALANCE / len(symbols)
            position = None; trades = []; closes = []; vols = []
            fee = 0.001  # 0.1% fee
            slippage = SLIPPAGE_LIQUID if sym in LIQUID_PAIRS else SLIPPAGE_NORMAL

            for candle in split_candles:
                closes.append(candle["close"]); vols.append(candle["volume"])
                if len(closes) < 50: continue
                price = candle["close"]

                if position:
                    pnl = ((price - position["entry"]) / position["entry"]) * 100
                    # Trailing
                    if pnl >= 10:
                        new_sl = price * (1 - TRAILING_STOP_PCT)
                        if new_sl > position["sl"]: position["sl"] = new_sl
                    # Partial TP1
                    if not position.get("tp1_done") and price >= position["tp1"]:
                        exec_p = price * (1 - slippage) * (1 - fee)
                        pnl_usd = (position["qty"] * 0.5) * exec_p - (position["amount"] * 0.5)
                        balance += position["amount"] * 0.5 + pnl_usd
                        position["qty"] *= 0.5; position["amount"] *= 0.5
                        position["tp1_done"] = True; position["sl"] = position["entry"]
                    elif price <= position["sl"] or price >= position.get("tp3", position["entry"] * (1 + TP3_PCT)):
                        exec_p = price * (1 - slippage) * (1 - fee)
                        pnl_usd = position["qty"] * exec_p - position["amount"]
                        balance += position["amount"] + pnl_usd
                        trades.append({"pnl_usd": pnl_usd, "pnl_pct": pnl}); position = None

                if not position:
                    rsi = calc_rsi(closes); macd = calc_macd(closes); bb = calc_bollinger(closes)
                    volr = calc_volume_ratio(vols); stoch = calc_stochastic_rsi(closes)
                    div = detect_rsi_divergence([{"high": c, "low": c*0.98, "close": c} for c in closes], closes)
                    st = calc_supertrend([{"high": c, "low": c*0.98, "close": c} for c in closes])
                    adx_r = calc_adx([{"high": c, "low": c*0.98, "close": c} for c in closes])
                    score = 0
                    if rsi < 35: score += 2
                    if st["is_uptrend"]: score += 2
                    if macd["histogram"] > 0: score += 1
                    if bb["percent_b"] < 0.3: score += 1
                    if stoch["signal"] == "OVERSOLD": score += 2
                    if div["bullish"]: score += 3
                    if adx_r["trend_strength"] != "WEAK": score += 1
                    if score >= MIN_VOTE_SCORE:
                        var = calc_var(closes)
                        exec_p = price * (1 + slippage) * (1 + fee)
                        amt = min(balance * CAPITAL_PER_TRADE, balance * 0.20)
                        if div["bullish"]: amt *= 1.3
                        if amt >= 5:
                            balance -= amt
                            sl = max(exec_p * (1 - var), exec_p * (1 - STOP_LOSS_PCT))
                            position = {"entry": exec_p, "amount": amt, "qty": amt / exec_p,
                                        "sl": sl, "tp1": exec_p * (1 + TP1_PCT),
                                        "tp3": exec_p * (1 + TP3_PCT), "tp1_done": False}

            if position:
                p = split_candles[-1]["close"]
                exec_p = p * (1 - slippage) * (1 - fee)
                pnl_usd = position["qty"] * exec_p - position["amount"]
                balance += position["amount"] + pnl_usd
                trades.append({"pnl_usd": pnl_usd, "pnl_pct": ((p - position["entry"]) / position["entry"]) * 100})

            wins = [t for t in trades if t["pnl_usd"] >= 0]
            ret = ((balance - PAPER_BALANCE / len(symbols)) / (PAPER_BALANCE / len(symbols))) * 100
            wr = len(wins) / len(trades) * 100 if trades else 0
            returns = [t["pnl_pct"] / 100 for t in trades]
            avg_r = sum(returns) / len(returns) if returns else 0
            std_r = (sum((r - avg_r) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5 if len(returns) > 1 else 1
            sharpe = round(avg_r / std_r, 2) if std_r else 0
            gp = sum(t["pnl_usd"] for t in trades if t["pnl_usd"] > 0)
            gl = abs(sum(t["pnl_usd"] for t in trades if t["pnl_usd"] < 0))
            pf = round(gp / gl, 2) if gl > 0 else float("inf")

            sym_results.append({"split": split_name, "trades": len(trades), "winrate": wr,
                                 "return": ret, "sharpe": sharpe, "pf": pf})
            c = Fore.GREEN if ret >= 0 else Fore.RED
            print(c + f"    {split_name}: {len(trades)} trades | WR:{wr:.0f}% | {ret:+.1f}% | Sharpe:{sharpe} | PF:{pf}")

        # Consistência entre splits (overfitting check)
        if len(sym_results) >= 2:
            test_ret = sym_results[-1]["return"] if sym_results else 0
            train_ret = sym_results[0]["return"] if sym_results else 0
            overfit = "⚠ POSSÍVEL OVERFITTING" if train_ret > 20 and test_ret < 0 else "✓ Consistente"
            print(f"    → {overfit}")
        all_results.extend(sym_results)

    # Resumo geral
    test_results = [r for r in all_results if r["split"] == "TESTE"]
    if test_results:
        print(Fore.CYAN + f"\n{'═'*55}")
        print(Fore.CYAN + "  📊 RESULTADO NO SET DE TESTE (dados nunca vistos)")
        print(Fore.CYAN + f"{'═'*55}")
        avg_ret = sum(r["return"] for r in test_results) / len(test_results)
        avg_wr  = sum(r["winrate"] for r in test_results) / len(test_results)
        avg_sh  = sum(r["sharpe"] for r in test_results) / len(test_results)
        avg_pf  = sum(r["pf"] for r in test_results if r["pf"] != float("inf")) / len(test_results)
        c = Fore.GREEN if avg_ret >= 0 else Fore.RED
        print(c + f"  Retorno médio: {avg_ret:+.1f}%")
        print(f"  Win rate médio: {avg_wr:.0f}%")
        print(f"  Sharpe médio: {avg_sh:.2f} (meta >1.5)")
        print(f"  Profit Factor: {avg_pf:.2f} (meta >1.5)")
        verdict = "✅ ESTRATÉGIA SÓLIDA" if avg_ret > 5 and avg_sh > 1.0 and avg_pf > 1.2 else "⚠ REVISAR PARÂMETROS"
        print(f"\n  {verdict}\n")


# ══════════════════════════════════════════
#  ARBITRAGEM TRIANGULAR (Monitor mode)
# ══════════════════════════════════════════

def scan_triangular_arbitrage() -> list:
    """
    Escaneia oportunidades de arbitragem triangular na Binance.
    Rota: USDT → A → B → USDT
    Lucro = (1 * p_AB_bid * p_BQ_bid / p_AQ_ask) - 1 - fees

    Modo monitor: detecta e exibe oportunidades, não executa.
    Execução real requer latência <100ms — inviável via API REST padrão.
    """
    if not ARB_ENABLED:
        return []

    opportunities = []

    # Busca todos os preços de uma vez (mais eficiente)
    try:
        all_prices_data = b_get("/api/v3/ticker/bookTicker")
        if not all_prices_data:
            return []
        price_map = {}
        for item in all_prices_data:
            sym = item.get("symbol","")
            price_map[sym] = {
                "bid": float(item.get("bidPrice", 0)),
                "ask": float(item.get("askPrice", 0))
            }
    except Exception as e:
        log.warning(f"ARB price fetch: {e}")
        return []

    fee3 = (1 - ARB_FEE_PCT) ** 3  # fator de custo para 3 trades

    for (a, b, q) in ARB_TRIANGLES:
        # Rota 1: USDT → A → B → USDT
        # Compra A/USDT, Compra B/A (ou vende A/B), Vende B/USDT
        try:
            # Leg 1: compra A com USDT
            sym_aq = f"{a}{q}"
            ask_aq = price_map.get(sym_aq, {}).get("ask", 0)
            if ask_aq <= 0: continue
            qty_a = 1.0 / ask_aq  # quantos A com 1 USDT

            # Leg 2: compra B com A (usando par B/A se existir)
            sym_ba = f"{b}{a}"
            sym_ab = f"{a}{b}"

            if sym_ba in price_map:
                ask_ba = price_map[sym_ba].get("ask", 0)
                if ask_ba <= 0: continue
                qty_b = qty_a / ask_ba
            elif sym_ab in price_map:
                bid_ab = price_map[sym_ab].get("bid", 0)
                if bid_ab <= 0: continue
                qty_b = qty_a * bid_ab
            else:
                continue  # par não existe

            # Leg 3: vende B por USDT
            sym_bq = f"{b}{q}"
            bid_bq = price_map.get(sym_bq, {}).get("bid", 0)
            if bid_bq <= 0: continue
            final_usdt = qty_b * bid_bq

            # Lucro líquido após taxas
            profit_pct = (final_usdt * fee3 - 1.0) * 100

            if profit_pct >= ARB_MIN_PROFIT_PCT:
                opportunities.append({
                    "route":      f"USDT→{a}→{b}→USDT",
                    "profit_pct": round(profit_pct, 4),
                    "leg1":       f"Buy {a}/USDT @ {ask_aq:.6f}",
                    "leg3":       f"Sell {b}/USDT @ {bid_bq:.6f}",
                    "timestamp":  datetime.now().strftime("%H:%M:%S"),
                })
        except Exception as e:
            continue

        # Rota 2: direção inversa — USDT → B → A → USDT
        try:
            sym_bq = f"{b}{q}"
            ask_bq = price_map.get(sym_bq, {}).get("ask", 0)
            if ask_bq <= 0: continue
            qty_b2 = 1.0 / ask_bq

            if sym_ba in price_map:
                bid_ba = price_map[sym_ba].get("bid", 0)
                if bid_ba <= 0: continue
                qty_a2 = qty_b2 * bid_ba
            elif sym_ab in price_map:
                ask_ab = price_map[sym_ab].get("ask", 0)
                if ask_ab <= 0: continue
                qty_a2 = qty_b2 / ask_ab
            else:
                continue

            sym_aq = f"{a}{q}"
            bid_aq = price_map.get(sym_aq, {}).get("bid", 0)
            if bid_aq <= 0: continue
            final_usdt2 = qty_a2 * bid_aq
            profit_pct2 = (final_usdt2 * fee3 - 1.0) * 100

            if profit_pct2 >= ARB_MIN_PROFIT_PCT:
                opportunities.append({
                    "route":      f"USDT→{b}→{a}→USDT",
                    "profit_pct": round(profit_pct2, 4),
                    "leg1":       f"Buy {b}/USDT @ {ask_bq:.6f}",
                    "leg3":       f"Sell {a}/USDT @ {bid_aq:.6f}",
                    "timestamp":  datetime.now().strftime("%H:%M:%S"),
                })
        except:
            continue

    # Ordena por lucro
    opportunities.sort(key=lambda x: x["profit_pct"], reverse=True)
    return opportunities[:5]  # top 5


def print_arb_results(opportunities: list):
    print(Fore.CYAN + f"\n{'─'*62}")
    print(Fore.CYAN + f"  🔄 ARBITRAGEM TRIANGULAR — {datetime.now().strftime('%H:%M:%S')}")
    print(Fore.CYAN + f"{'─'*62}")

    if not opportunities:
        print(f"  Nenhuma oportunidade ≥ {ARB_MIN_PROFIT_PCT}% encontrada neste ciclo.")
        print(f"  (Normal — oportunidades reais são raras e duram <1 segundo)")
        return

    print(Fore.GREEN + f"  {len(opportunities)} oportunidade(s) encontrada(s)!\n")
    for opp in opportunities:
        profit_color = Fore.GREEN if opp["profit_pct"] >= 0.3 else Fore.YELLOW
        print(profit_color + f"  💰 {opp['route']}")
        print(f"     Lucro líq.: {opp['profit_pct']:+.4f}% | {opp['leg1']} | {opp['leg3']}")
        print(f"     ⚠ Modo monitor — execução manual requer latência <100ms")
        print()


# ══════════════════════════════════════════
#  WATCHLIST DINÂMICA — rotação por performance
# ══════════════════════════════════════════

def load_asset_scores() -> dict:
    """Carrega scores históricos por ativo."""
    try:
        with open(ASSET_SCORE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_asset_scores(scores: dict):
    with open(ASSET_SCORE_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2, ensure_ascii=False)

def update_asset_score(state: dict):
    """
    Atualiza o score de cada ativo baseado em trades fechados.
    Ativos com boa performance sobem no ranking.
    Ativos com perdas consistentes podem ser removidos da watchlist.
    """
    if not DYNAMIC_WATCHLIST_ENABLED:
        return

    scores = load_asset_scores()
    sells  = [t for t in state.get("history",[]) if t["action"] == "SELL"]

    for trade in sells:
        sym     = trade.get("symbol","")
        pnl_pct = trade.get("pnl_pct", 0)
        if not sym: continue

        if sym not in scores:
            scores[sym] = {"wins":0,"losses":0,"total_pnl":0,"trades":0,"score":5.0}

        s = scores[sym]
        s["trades"]    += 1
        s["total_pnl"] += pnl_pct
        if pnl_pct >= 0:
            s["wins"]   += 1
            s["score"]   = min(10.0, s["score"] + 0.3)
        else:
            s["losses"] += 1
            s["score"]   = max(1.0,  s["score"] - 0.5)

        s["winrate"]   = round(s["wins"] / s["trades"] * 100, 1)
        s["avg_pnl"]   = round(s["total_pnl"] / s["trades"], 2)
        scores[sym]    = s

    save_asset_scores(scores)
    return scores

def get_dynamic_watchlist(base_watchlist: list) -> list:
    """
    Retorna watchlist ordenada por score — melhores ativos primeiro.
    Ativos com score < 2.0 e mais de 5 trades são candidatos à remoção.
    """
    if not DYNAMIC_WATCHLIST_ENABLED:
        return base_watchlist

    scores = load_asset_scores()
    if not scores:
        return base_watchlist

    # Ordena por score (melhores primeiro), mantendo ativos sem histórico no meio
    def sort_key(sym):
        if sym in scores and scores[sym]["trades"] >= 3:
            return -scores[sym]["score"]
        return -5.0  # neutro para ativos sem histórico

    sorted_wl = sorted(base_watchlist, key=sort_key)

    # Filtra ativos com performance muito ruim (score < 2 e +5 trades)
    filtered = [s for s in sorted_wl
                if s not in scores
                or scores[s]["trades"] < 5
                or scores[s]["score"] >= 2.0]

    return filtered[:DYNAMIC_MAX_SIZE]

def print_asset_scores():
    """Imprime ranking de performance por ativo."""
    scores = load_asset_scores()
    if not scores:
        print(f"  Sem histórico de trades por ativo ainda.")
        return
    ranked = sorted(scores.items(), key=lambda x: -x[1].get("score",5))
    print(Fore.CYAN + f"\n  📊 RANKING DE ATIVOS (baseado em {sum(s['trades'] for _,s in ranked)} trades)")
    print(f"  {'SYM':<8} {'SCORE':>6} {'WR':>6} {'AVG':>7} {'TRADES':>7}")
    print(f"  {'─'*40}")
    for sym, s in ranked:
        if s["trades"] < 1: continue
        c = Fore.GREEN if s["score"] >= 6 else Fore.RED if s["score"] < 3 else Fore.YELLOW
        print(c + f"  {sym:<8} {s['score']:>5.1f}/10 {s.get('winrate',0):>5.0f}% {s.get('avg_pnl',0):>+6.1f}% {s['trades']:>7}")


# ══════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest",  action="store_true")
    parser.add_argument("--days",      type=int, default=90)
    parser.add_argument("--live",      action="store_true")
    parser.add_argument("--optimize",  action="store_true")
    parser.add_argument("--research",  action="store_true")
    parser.add_argument("--status",    action="store_true")
    parser.add_argument("--arb",       action="store_true", help="Roda só o scanner de arbitragem")
    parser.add_argument("--scores",    action="store_true", help="Mostra ranking de performance por ativo")
    args = parser.parse_args()

    if "SUA_" in BINANCE_API_KEY or "SUA_" in CLAUDE_API_KEY:
        print(Fore.RED + "\n  ⚠  Configure: BINANCE_API_KEY, BINANCE_API_SECRET, CLAUDE_API_KEY\n"); sys.exit(1)

    if args.backtest: run_backtest(args.days); sys.exit(0)
    state = load_state()
    if args.optimize: auto_optimize(state); save_state(state); sys.exit(0)
    if args.research: auto_research(); state["last_research"] = datetime.now().strftime("%Y-%m-%d"); save_state(state); sys.exit(0)
    if args.status:   print_status(state); sys.exit(0)
    if args.scores:   print_asset_scores(); sys.exit(0)
    if args.arb:
        print(Fore.CYAN + "\n  🔄 Scanner de Arbitragem Triangular — Binance")
        print(f"  Mínimo de lucro: {ARB_MIN_PROFIT_PCT}% | Taxas: {ARB_FEE_PCT*100:.1f}% × 3 trades\n")
        opps = scan_triangular_arbitrage()
        print_arb_results(opps)
        sys.exit(0)

    mode = "live" if args.live else "paper"
    if mode == "live":
        print(Fore.RED + "\n  ⚠  MODO LIVE! Enter para confirmar..."); input()

    kelly = kelly_position_size(state)
    news_enabled = "✅" if CRYPTOPANIC_TOKEN else "❌"
    arb_enabled  = "✅" if ARB_ENABLED else "❌"

    print(Fore.CYAN + """
╔══════════════════════════════════════════════════════════════╗
║   TRADING BOT v9 — BTC+ETH+ALTCOINS                         ║
║   25 Indicadores · Arbitragem Triangular · Watchlist Dinâm. ║
║   Ichimoku · CMF · CCI · HMA · Pivots · Williams %R         ║
╚══════════════════════════════════════════════════════════════╝""")
    active_wl = get_dynamic_watchlist(WATCHLIST)
    print(f"  Modo: {'🔴 LIVE' if mode=='live' else '🟡 PAPER'} | ${state['balance']:.2f} | {INTERVAL_MINUTES}min")
    print(f"  Kelly:{kelly*100:.1f}% | Watchlist: {len(active_wl)} ativos | Spread max:{MAX_SPREAD_PCT}%")
    print(f"  Arbitragem:{arb_enabled} (min {ARB_MIN_PROFIT_PCT}%) | CryptoPanic:{news_enabled}\n")

    while True:
        try:
            run_cycle(state, mode)
            print(f"  ⏰ Próxima análise em {INTERVAL_MINUTES} min. Ctrl+C para parar.\n")
            time.sleep(INTERVAL_MINUTES * 60)
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\n\n  Bot encerrado.")
