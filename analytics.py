import json
import os

STATS_FILE = "stats.json"

# 📊 DEFAULT
DEFAULT_STATS = {
    "users": 0,
    "messages": 0,
    "revenue": 0,
    "active_users": 0
}

# 🔄 CARICA STATS
def get_stats():
    if not os.path.exists(STATS_FILE):
        return DEFAULT_STATS.copy()

    try:
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    except:
        return DEFAULT_STATS.copy()

# 💾 SALVA STATS
def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=4)

# ➕ AGGIORNA GENERICO
def update_stat(key, value=1):
    stats = get_stats()

    if key not in stats:
        stats[key] = 0

    stats[key] += value

    save_stats(stats)

# 👤 NUOVO UTENTE
def track_user():
    update_stat("users")

# 💬 MESSAGGI
def track_message():
    update_stat("messages")

# 💰 REVENUE
def track_revenue(amount):
    stats = get_stats()
    stats["revenue"] += amount
    save_stats(stats)

# 🟢 UTENTI ATTIVI
def track_active():
    update_stat("active_users")