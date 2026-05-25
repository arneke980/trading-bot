"""
Trading Signal Bot
-------------------
Monitort crypto + aandelen elke 5 minuten.
Stuurt BUY/SELL signalen met entry, stoploss en take profit via Telegram.

INSTALLEER:
pip install python-telegram-bot yfinance pandas ta asyncio

GEBRUIK:
python trading_signal_bot.py
"""

import asyncio
import yfinance as yf
import pandas as pd
import ta
from telegram import Bot
from telegram.error import TelegramError
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
TOKEN   = "8739733759:AAFM8SpzZy9MAHWkQpbtPr_ZnQsrB4NeeuM"
CHAT_ID = "7168878123"

CHECK_INTERVAL = 300  # 5 minuten in seconden

# Welke assets monitoren
CRYPTO  = ["BTC-USD", "ETH-USD", "SOL-USD"]
STOCKS  = ["AAPL", "TSLA", "NVDA", "AMZN"]
FUTURES = [
    "ES=F",   # S&P 500 Futures
    "NQ=F",   # Nasdaq 100 Futures
    "YM=F",   # Dow Jones Futures
]

ALL_ASSETS = CRYPTO + STOCKS + FUTURES
# ─────────────────────────────────────────────────────────────────────────────

bot = Bot(token=TOKEN)


async def send_signal(message: str):
    """Stuur een signaal via Telegram."""
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Signaal gestuurd!")
    except TelegramError as e:
        print(f"Telegram error: {e}")


def get_data(symbol: str) -> pd.DataFrame | None:
    """Haal de laatste 60 candles op (1u interval)."""
    try:
        df = yf.download(symbol, period="5d", interval="1h", progress=False, auto_adjust=True)
        if df.empty or len(df) < 20:
            return None
        df.dropna(inplace=True)
        return df
    except Exception as e:
        print(f"Data error voor {symbol}: {e}")
        return None


def analyze(symbol: str, df: pd.DataFrame) -> dict | None:
    """
    Analyseer de data met RSI, MACD en EMA.
    Geeft een signaal terug als de condities kloppen.
    """
    try:
        close = df["Close"].squeeze()

        # Indicatoren berekenen
        rsi   = ta.momentum.RSIIndicator(close, window=14).rsi()
        macd  = ta.trend.MACD(close)
        ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator()
        ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator()

        last_rsi       = rsi.iloc[-1]
        last_macd      = macd.macd().iloc[-1]
        last_signal    = macd.macd_signal().iloc[-1]
        last_ema20     = ema20.iloc[-1]
        last_ema50     = ema50.iloc[-1]
        current_price  = close.iloc[-1]

        signal = None

        # ── BUY condities ──────────────────────────────────────────────────
        # RSI oversold + MACD bullish crossover + prijs boven EMA20
        if (last_rsi < 40
                and last_macd > last_signal
                and current_price > last_ema20):
            signal = "BUY"

        # ── SELL condities ─────────────────────────────────────────────────
        # RSI overbought + MACD bearish crossover + prijs onder EMA20
        elif (last_rsi > 60
                and last_macd < last_signal
                and current_price < last_ema20):
            signal = "SELL"

        if signal is None:
            return None

        # Stoploss en take profit berekenen
        atr = ta.volatility.AverageTrueRange(
            df["High"].squeeze(),
            df["Low"].squeeze(),
            close,
            window=14
        ).average_true_range().iloc[-1]

        if signal == "BUY":
            stoploss    = round(current_price - (1.5 * atr), 4)
            take_profit = round(current_price + (3.0 * atr), 4)
        else:
            stoploss    = round(current_price + (1.5 * atr), 4)
            take_profit = round(current_price - (3.0 * atr), 4)

        return {
            "symbol":       symbol,
            "signal":       signal,
            "price":        round(current_price, 4),
            "stoploss":     stoploss,
            "take_profit":  take_profit,
            "rsi":          round(last_rsi, 2),
            "ema20":        round(last_ema20, 4),
            "ema50":        round(last_ema50, 4),
        }

    except Exception as e:
        print(f"Analyse error voor {symbol}: {e}")
        return None


def format_signal(data: dict) -> str:
    """Maak een mooi Telegram bericht van het signaal."""
    emoji = "🟢" if data["signal"] == "BUY" else "🔴"
    arrow = "📈" if data["signal"] == "BUY" else "📉"
    time  = datetime.now().strftime("%d/%m/%Y %H:%M")

    return (
        f"{emoji} *{data['signal']} SIGNAAL — {data['symbol']}* {arrow}\n"
        f"──────────────────────\n"
        f"⏰ *Tijd:* `{time}`\n"
        f"💰 *Entry prijs:* `{data['price']}`\n"
        f"🛑 *Stop Loss:* `{data['stoploss']}`\n"
        f"🎯 *Take Profit:* `{data['take_profit']}`\n"
        f"──────────────────────\n"
        f"📊 *RSI:* `{data['rsi']}`\n"
        f"📉 *EMA20:* `{data['ema20']}`\n"
        f"📉 *EMA50:* `{data['ema50']}`\n"
        f"──────────────────────\n"
        f"⚠️ _Dit is geen financieel advies. Trade op eigen risico._"
    )


async def run_bot():
    """Hoofdloop — checkt elke 5 minuten alle assets."""
    print("🚀 Trading Signal Bot gestart!")
    print(f"📊 Monitoring: {', '.join(ALL_ASSETS)}")
    print(f"⏱️  Interval: elke {CHECK_INTERVAL // 60} minuten\n")

    await send_signal(
        "🚀 *Trading Signal Bot is gestart!*\n\n"
        f"📊 Monitoring: {', '.join(ALL_ASSETS)}\n"
        f"⏱️ Check elke 5 minuten\n\n"
        "_Wachten op signalen..._"
    )

    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Markt aan het analyseren...")

        for symbol in ALL_ASSETS:
            df = get_data(symbol)
            if df is None:
                print(f"  ⚠️  Geen data voor {symbol}")
                continue

            result = analyze(symbol, df)

            if result:
                message = format_signal(result)
                print(f"  ✅ Signaal gevonden voor {symbol}: {result['signal']}")
                await send_signal(message)
            else:
                print(f"  ➖ Geen signaal voor {symbol}")

            await asyncio.sleep(1)  # korte pauze tussen requests

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Analyse klaar. Wachten 5 minuten...")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_bot())
