#!/bin/bash
mkdir -p /opt/bitvavo-bot
cd /opt/bitvavo-bot

cat > config.json <<'EOF'
{
  "market": "BTC-EUR",
  "start_balance": 500,
  "trade_eur": 100,
  "take_profit_pct": 2.0,
  "stop_loss_pct": 1.0,
  "daily_max_loss": -10,
  "daily_max_profit": 10,
  "max_trades_per_day": 3,
  "check_seconds": 60,
  "dry_run": true
}
EOF

cat > bot.py <<'EOF'
import requests, time, json, os
from datetime import datetime, date

BASE="/opt/bitvavo-bot"
CONFIG=f"{BASE}/config.json"
STATE=f"{BASE}/state.json"
STATUS=f"{BASE}/status.json"
LOG=f"{BASE}/trades.log"

def load_config():
    with open(CONFIG) as f:
        return json.load(f)

cfg=load_config()

state={
    "balance": cfg["start_balance"],
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

def status(data):
    with open(STATUS,"w") as f:
        json.dump(data,f,indent=2)

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

def buy(price):
    btc=cfg["trade_eur"]/price
    state["balance"]-=cfg["trade_eur"]
    state["in_position"]=True
    state["buy_price"]=price
    state["btc_amount"]=btc
    log(f"DRY-RUN KOOP €{cfg['trade_eur']:.2f} BTC op €{price:.2f}")

def sell(price, reason):
    value=state["btc_amount"]*price
    profit=value-cfg["trade_eur"]
    state["balance"]+=value
    state["trades"]+=1
    state["daily_trades"]+=1
    state["daily_profit"]+=profit
    if profit>=0:
        state["wins"]+=1
    else:
        state["losses"]+=1
    log(f"DRY-RUN VERKOOP {reason}: €{profit:.2f} | saldo €{state['balance']:.2f}")
    state["in_position"]=False
    state["buy_price"]=0
    state["btc_amount"]=0

log("Bitvavo Bot V2 gestart - DRY-RUN")

while True:
    try:
        cfg=load_config()
        reset_day()

        closes=candles()
        price=closes[-1]
        ema20=ema(closes[-30:],20)
        ema50=ema(closes[-60:],50)
        rr=rsi(closes)

        status({
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
            "dry_run": cfg["dry_run"],
            "updated": datetime.now().isoformat()
        })

        if state["daily_profit"]<=cfg["daily_max_loss"]:
            log(f"Dagstop verlies bereikt €{state['daily_profit']:.2f}")
            time.sleep(cfg["check_seconds"])
            continue

        if state["daily_profit"]>=cfg["daily_max_profit"]:
            log(f"Dagdoel bereikt €{state['daily_profit']:.2f}")
            time.sleep(cfg["check_seconds"])
            continue

        if state["daily_trades"]>=cfg["max_trades_per_day"]:
            log("Max trades vandaag bereikt")
            time.sleep(cfg["check_seconds"])
            continue

        if not state["in_position"]:
            log(f"Koers €{price:.2f} | EMA20 {ema20:.2f} | EMA50 {ema50:.2f} | RSI {rr:.1f} | saldo €{state['balance']:.2f}")
            if ema20>ema50 and 35<=rr<=55 and closes[-1]>closes[-2] and state["balance"]>=cfg["trade_eur"]:
                buy(price)
        else:
            result=((price-state["buy_price"])/state["buy_price"])*100
            log(f"Koers €{price:.2f} | gekocht €{state['buy_price']:.2f} | resultaat {result:.2f}%")
            if result>=cfg["take_profit_pct"]:
                sell(price,"WINST")
            elif result<=-cfg["stop_loss_pct"]:
                sell(price,"STOP-LOSS")

        save()
        time.sleep(cfg["check_seconds"])

    except Exception as e:
        log(f"FOUT: {e}")
        time.sleep(60)
EOF

cat > /etc/systemd/system/bitvavo-bot.service <<'EOF'
[Unit]
Description=Bitvavo Bot V2
After=network-online.target

[Service]
WorkingDirectory=/opt/bitvavo-bot
ExecStart=/opt/bitvavo-bot/venv/bin/python /opt/bitvavo-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable bitvavo-bot
systemctl restart bitvavo-bot
echo "Bitvavo Bot V2 geïnstalleerd"
