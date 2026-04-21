def smart_upsell(user_data):
    if user_data["plan"] == "free":
        return "🔥 Stai usando la versione FREE. Passa a PRO per sbloccare AI illimitata + immagini!"

    if user_data["messages_used"] > 150:
        return "⚡ Stai per finire i messaggi. Upgrade ora per continuare!"

    return None


def dynamic_price():
    # prezzo dinamico (psicologia marketing)
    import random
    return random.choice([7, 9, 12])