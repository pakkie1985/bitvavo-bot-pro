import time
from indicators import ema, rsi
from market import get_candles
from homeassistant import get_settings

MARKET = "BTC-EUR"

print("Bitvavo Bot Pro v6 + Home Assistant test gestart")

while True:
    settings = get_settings()

    closes = get_candles(MARKET)
    price = closes[-1]
    ema20 = ema(closes[-30:], 20)
    ema50 = ema(closes[-60:], 50)
    rr = rsi(closes)

    print(
        f"Bot {'AAN' if settings['bot_on'] else 'UIT'} | "
        f"Live {'JA' if settings['live'] else 'NEE'} | "
        f"Trade €{settings['trade_eur']} | TP {settings['take_profit']}% | SL {settings['stop_loss']}% | "
        f"Koers €{price:.2f} | EMA20 {ema20:.2f} | EMA50 {ema50:.2f} | RSI {rr:.1f}"
    )

    time.sleep(60)
