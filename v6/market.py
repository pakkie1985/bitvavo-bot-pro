import requests


def get_candles(market="BTC-EUR", interval="5m", limit=60):
    r = requests.get(
        f"https://api.bitvavo.com/v2/{market}/candles",
        params={"interval": interval, "limit": limit},
        timeout=10
    )
    r.raise_for_status()
    return [float(c[4]) for c in reversed(r.json())]
