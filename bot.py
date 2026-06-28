import requests, time, json, os
from datetime import datetime, date

BASE="/opt/bitvavo-bot"
CONFIG=f"{BASE}/config.json"
STATE=f"{BASE}/state.json"
STATUS=f"{BASE}/status.json"
LOG=f"{BASE}/trades.log"
HA_ENV=f"{BASE}/ha.env"

def load_env():
    env={}
    if os.path.exists(HA_ENV):
        for line in open(HA_ENV):
            if "=" in line:
                k,v=line.strip().split("=",1)
                env[k]=v
    return env

def load_config():
    return json.load(open(CONFIG))

cfg=load_config()
ha=load_env()

state={
    "balance": 500.0,
    "in_position": False,
    "buy_price": 0.0,
    "btc_amount": 0.0,
    "position_cost": 0.0,
    "highest_price": 0.0,
    "trades": 0,
    "wins": 0,
    "losses": 0,
    "day": str(date.today()),
    "daily_profit": 0.0,
    "daily_trades": 0
}

if os.path.exists(STATE):
    state.update(json.load(open(STATE)))

def log(msg):
    line=f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {msg}"
    print(line, flush=True)
    open(LOG,"a").write(line+"\n")

def save():
    json.dump(state, open(STATE,"w"), indent=2)

def ha_get(entity, default):
    try:
        r=requests.get(
            f"{ha['HA_URL']}/api/states/{entity}",
            headers={"Authorization":f"Bearer {ha['HA_TOKEN']}"},
            timeout=8
        )
        return r.json().get("state", default)
    except:
        return default

def settings():
    return {
        "bot_on": ha_get("input_boolean.bitvavo_bot_aan","off") == "on",
        "live": ha_get("input_boolean.bitvavo_bot_live_modus","off") == "on",
        "trade_eur": float(ha_get("input_number.bitvavo_handelsbedrag",100)),
        "tp": float(ha_get("input_number.bitvavo_take_profit",2)),
        "sl": float(ha_get("input_number.bitvavo_stop_loss",1)),
        "trail": 0.7
    }

def candles():
    r=requests.get(
        f"https://api.bitvavo.com/v2/{cfg['market']}/candles",
        params={"interval":"5m","limit":60},
        timeout=10
    )
    r.raise_for_status()
    return [float(c[4]) for c in reversed(r.json())]

def ema(vals, period):
    k=2/(period+1)
    e=vals[0]
    for v in vals[1:]:
        e=v*k+e*(1-k)
    return e

def rsi(vals, period=14):
    gains=[]; losses=[]
    for i in range(1,len(vals)):
        d=vals[i]-vals[i-1]
        gains.append(max(d,0))
        losses.append(abs(min(d,0)))
    ag=sum(gains[-period:])/period
    al=sum(losses[-period:])/period
    if al==0:
        return 100
    rs=ag/al
    return 100-(100/(1+rs))

def reset_day():
    today=str(date.today())
    if state["day"] != today:
        state["day"]=today
        state["daily_profit"]=0.0
        state["daily_trades"]=0
        log("Nieuwe handelsdag gestart")

def buy(price, amount):
    btc=amount/price
    state["balance"] -= amount
    state["in_position"] = True
    state["buy_price"] = price
    state["btc_amount"] = btc
    state["position_cost"] = amount
    state["highest_price"] = price
    log(f"PAPER KOOP €{amount:.2f} BTC op €{price:.2f}")

def sell(price, reason):
    value = state["btc_amount"] * price
    cost = state["position_cost"]
    profit = value - cost
    result_pct = (profit / cost) * 100 if cost > 0 else 0

    state["balance"] += value
    state["trades"] += 1
    state["daily_trades"] += 1
    state["daily_profit"] += profit

    if profit >= 0:
        state["wins"] += 1
    else:
        state["losses"] += 1

    log(f"PAPER VERKOOP {reason}: winst €{profit:.2f} ({result_pct:.2f}%) | saldo €{state['balance']:.2f}")

    state["in_position"] = False
    state["buy_price"] = 0.0
    state["btc_amount"] = 0.0
    state["position_cost"] = 0.0
    state["highest_price"] = 0.0

def write_status(price, ema20, ema50, rr, s):
    open_winst = 0.0
    result_pct = 0.0
    open_value = 0.0

    if state["in_position"]:
        open_value = state["btc_amount"] * price
        open_winst = open_value - state["position_cost"]
        result_pct = (open_winst / state["position_cost"]) * 100 if state["position_cost"] > 0 else 0

    json.dump({
        "market": cfg["market"],
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rr,
        "balance": state["balance"],
        "in_position": state["in_position"],
        "buy_price": state["buy_price"],
        "btc_amount": state["btc_amount"],
        "position_cost": state["position_cost"],
        "open_value": open_value,
        "open_profit": open_winst,
        "result_pct": result_pct,
        "daily_profit": state["daily_profit"],
        "daily_trades": state["daily_trades"],
        "trades": state["trades"],
        "wins": state["wins"],
        "losses": state["losses"],
        "dry_run": not s["live"],
        "bot_on": s["bot_on"],
        "trade_eur": s["trade_eur"],
        "take_profit": s["tp"],
        "stop_loss": s["sl"],
        "updated": datetime.now().isoformat()
    }, open(STATUS,"w"), indent=2)

log("Bitvavo Bot Pro v5 gestart - veilige paper trading")

while True:
    try:
        cfg=load_config()
        s=settings()
        reset_day()

        closes=candles()
        price=closes[-1]
        ema20=ema(closes[-30:],20)
        ema50=ema(closes[-60:],50)
        rr=rsi(closes)

        write_status(price, ema20, ema50, rr, s)

        if state["daily_profit"] <= cfg.get("daily_max_loss",-10):
            log(f"Dagstop verlies bereikt €{state['daily_profit']:.2f}")
            time.sleep(cfg.get("check_seconds",60))
            continue

        if state["daily_profit"] >= cfg.get("daily_max_profit",10):
            log(f"Dagdoel bereikt €{state['daily_profit']:.2f}")
            time.sleep(cfg.get("check_seconds",60))
            continue

        if state["daily_trades"] >= cfg.get("max_trades_per_day",3):
            log("Max trades vandaag bereikt")
            time.sleep(cfg.get("check_seconds",60))
            continue

        if not state["in_position"]:
            log(f"Bot {'AAN' if s['bot_on'] else 'UIT'} | Koers €{price:.2f} | EMA20 {ema20:.2f} | EMA50 {ema50:.2f} | RSI {rr:.1f}")

            if s["bot_on"] and ema20 > ema50 and 35 <= rr <= 55 and closes[-1] > closes[-2] and state["balance"] >= s["trade_eur"]:
                buy(price, s["trade_eur"])

        else:
            if price > state["highest_price"]:
                state["highest_price"] = price

            profit_pct = ((price - state["buy_price"]) / state["buy_price"]) * 100
            drop_from_high = ((state["highest_price"] - price) / state["highest_price"]) * 100

            log(f"Koers €{price:.2f} | gekocht €{state['buy_price']:.2f} | resultaat {profit_pct:.2f}% | trail {drop_from_high:.2f}%")

            if profit_pct >= s["tp"]:
                sell(price, "TAKE-PROFIT")

            elif profit_pct >= 1.0 and drop_from_high >= s["trail"]:
                sell(price, "TRAILING-STOP")

            elif profit_pct <= -s["sl"]:
                sell(price, "STOP-LOSS")

        save()
        time.sleep(cfg.get("check_seconds",60))

    except Exception as e:
        log(f"FOUT: {e}")
        time.sleep(60)
