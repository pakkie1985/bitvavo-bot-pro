def should_buy(price, ema20, ema50, rsi, previous_close, balance, trade_eur, bot_on):
    if not bot_on:
        return False, "Bot staat uit"

    if balance < trade_eur:
        return False, "Onvoldoende saldo"

    if ema20 <= ema50:
        return False, "Trend niet bullish"

    if not (35 <= rsi <= 55):
        return False, "RSI buiten koopzone"

    if price <= previous_close:
        return False, "Nog geen herstel candle"

    return True, "Koopsignaal bevestigd"


def should_sell(price, buy_price, highest_price, take_profit, stop_loss, trailing_stop=0.7):
    if buy_price <= 0:
        return False, "Geen koopprijs"

    profit_pct = ((price - buy_price) / buy_price) * 100

    if profit_pct >= take_profit:
        return True, "TAKE-PROFIT"

    if profit_pct <= -stop_loss:
        return True, "STOP-LOSS"

    if highest_price > buy_price:
        drop_from_high = ((highest_price - price) / highest_price) * 100

        if profit_pct >= 1.0 and drop_from_high >= trailing_stop:
            return True, "TRAILING-STOP"

    return False, "Vasthouden"


def signal_score(ema20, ema50, rsi, price, previous_close):
    score = 0

    if ema20 > ema50:
        score += 35

    if 35 <= rsi <= 55:
        score += 35

    if price > previous_close:
        score += 20

    if rsi < 70:
        score += 10

    return min(score, 100)
