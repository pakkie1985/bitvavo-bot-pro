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
        with open(HA_ENV) as f:
            for line in f:
                if "=" in line:
                    k,v=line.strip().split("=",1)
                    env[k]=v
    return env

def load_config():
    with open(CONFIG) as f:
        return json.load(f)

cfg=load_config()
ha=load_env()

state={
    "balance": cfg.get("start_balance",500),
    "in_position": False,
    "buy_price": 0,
    "btc_amount": 0,
    "trades": 0,
    "wins": 0,
    "losses": 0,
    "day": str(date.today()),
    "daily_profit": 0,
    "daily_trades": 0
}

if os.path.exists(STATE):
    with open(STATE) as f:
        state.update(json.load(f))

def log(msg):
    line=f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {msg}"
    print(line, flush=True)
    with open(LOG,"a") as f:
        f.write(line+"\n")

def save():
    with open(STATE,"w") as f:
        json.dump(state,f,indent=2)

def write_status(data):
    with open(STATUS,"w") as f:
        json.dump(data,f,indent=2)

def ha_get(entity, default=None):
    try:
        url=f"{ha['HA_URL']}/api/states/{entity}"
        headers={"Authorization":f"Bearer {ha['HA_TOKEN']}"}
        r=requests.get(url,headers=headers,timeout=8)
        r.raise_for_status()
        return r.json().get("state", default)
    except Exception:
        return default

def get_settings():
    bot_on = ha_get("input_boolean.bitvavo_bot_aan","off") == "on"
    live = ha_get("input_boolean.bitvavo_bot_live_modus","off") == "on"

    trade_eur = float(ha_get("input_number.bitvavo_handelsbedrag", cfg.get("trade_eur",100)))
    take_profit = float(ha_get("input_number.bitvavo_take_profit", cfg.get("take_profit_pct",2)))
    stop_loss = float(ha_get("input_number.bitvavo_stop_loss", cfg.get("stop_loss_pct",1)))

    return {
        "bot_on": bot_on,
        "live": live,
        "trade_eur": trade_eur,
        "take_profit": take_profit,
        "stop_loss": stop_loss
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
    if state["day"]!=today:
        state["day"]=today
        state["daily_profit"]=0
        state["daily_trades"]=0
        log("Nieuwe handelsdag gestart")

def buy(price, amount):
    btc=amount/price
    state["balance"]-=amount
    state["in_position"]=True
    state["buy_price"]=price
    state["btc_amount"]=btc
    log(f"PAPER KOOP €{amount:.2f} BTC op €{price:.2f}")

def sell(price, reason, amount):
    value=state["btc_amount"]*price
    profit=value-amount

    state["balance"]+=value
    state["trades"]+=1
    state["daily_trades"]+=1
    state["daily_profit"]+=profit

    if profit>=0:
        state["wins"]+=1
    else:
        state["losses"]+=1

    log(f"PAPER VERKOOP {reason}: €{profit:.2f} | saldo €{state['balance']:.2f}")

    state["in_position"]=False
    state["buy_price"]=0
    state["btc_amount"]=0

log("Bitvavo Bot Pro v3 gestart - Home Assistant bediening actief")

while True:
    try:
        cfg=load_config()
        settings=get_settings()
        reset_day()

        closes=candles()
        price=closes[-1]
        ema20=ema(closes[-30:],20)
        ema50=ema(closes[-60:],50)
        rr=rsi(closes)

        write_status({
            "market": cfg["market"],
            "price": price,
            "ema20": ema20,
            "ema50": ema50,
            "rsi": rr,
            "balance": state["balance"],
            "in_position": state["in_position"],
            "buy_price": state["buy_price"],
            "daily_profit": state["daily_profit"],
            "daily_trades": state["daily_trades"],
            "trades": state["trades"],
            "wins": state["wins"],
            "losses": state["losses"],
            "dry_run": not settings["live"],
            "bot_on": settings["bot_on"],
            "trade_eur": settings["trade_eur"],
            "take_profit": settings["take_profit"],
            "stop_loss": settings["stop_loss"],
            "updated": datetime.now().isoformat()
        })

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
            log(f"Bot {'AAN' if settings['bot_on'] else 'UIT'} | Koers €{price:.2f} | EMA20 {ema20:.2f} | EMA50 {ema50:.2f} | RSI {rr:.1f}")

            if settings["bot_on"]:
                if ema20>ema50 and 35<=rr<=55 and closes[-1]>closes[-2] and state["balance"]>=settings["trade_eur"]:
                    buy(price, settings["trade_eur"])

        else:
            result=((price-state["buy_price"])/state["buy_price"])*100
            log(f"Koers €{price:.2f} | gekocht €{state['buy_price']:.2f} | resultaat {result:.2f}%")

            if result >= settings["take_profit"]:
                sell(price,"WINST",settings["trade_eur"])

            elif result <= -settings["stop_loss"]:
                sell(price,"STOP-LOSS",settings["trade_eur"])

        save()
        time.sleep(cfg.get("check_seconds",60))

    except Exception as e:
        log(f"FOUT: {e}")
        time.sleep(60)
