import os
import requests


BASE = "/opt/bitvavo-bot/v6"
ENV_FILE = f"{BASE}/ha.env"


def load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    env[k] = v
    return env


env = load_env()


def get_state(entity_id, default=None):
    try:
        r = requests.get(
            f"{env['HA_URL']}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {env['HA_TOKEN']}"},
            timeout=8,
        )
        r.raise_for_status()
        return r.json().get("state", default)
    except Exception:
        return default


def get_settings():
    return {
        "bot_on": get_state("input_boolean.bitvavo_bot_aan", "off") == "on",
        "live": get_state("input_boolean.bitvavo_bot_live_modus", "off") == "on",
        "trade_eur": float(get_state("input_number.bitvavo_handelsbedrag", 100)),
        "take_profit": float(get_state("input_number.bitvavo_take_profit", 2)),
        "stop_loss": float(get_state("input_number.bitvavo_stop_loss", 1)),
    }
