import os
from dotenv import load_dotenv

# Charge le fichier .env à la racine du projet
# (là où tu lances `python bot.py`)
load_dotenv()

# ============================
#  Variables d'environnement
# ============================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN manquant dans .env")

COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

# IDs de salons / rôles (optionnels mais on cast en int si présents)
def _get_int_env(name: str, default: int | None = None) -> int | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        raise RuntimeError(f"Variable {name} invalide dans .env (doit être un entier)")

DAILY_CHANNEL_ID   = _get_int_env("DAILY_CHANNEL_ID")
REPORT_CHANNEL_ID  = _get_int_env("REPORT_CHANNEL_ID")
DIRECTION_ROLE_ID  = _get_int_env("DIRECTION_ROLE_ID")

# Horaires programmés
DAILY_QUESTION_HOUR = int(os.getenv("DAILY_QUESTION_HOUR", "18"))
REPORT_WEEKDAY      = int(os.getenv("REPORT_WEEKDAY", "0"))  # 0 = lundi
REPORT_HOUR         = int(os.getenv("REPORT_HOUR", "9"))
