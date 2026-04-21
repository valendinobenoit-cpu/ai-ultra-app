import json
import os
import random

BRAIN_FILE = "brain_data.json"

def load_brain():
    if not os.path.exists(BRAIN_FILE):
        return {}
    return json.load(open(BRAIN_FILE))

def save_brain(data):
    json.dump(data, open(BRAIN_FILE, "w"), indent=4)

# 🧠 PERSONALITÀ DINAMICA
def get_personality(user):
    data = load_brain()

    if user not in data:
        data[user] = {
            "tone": random.choice(["amichevole", "professionale", "ironico"]),
            "style": random.choice(["breve", "dettagliato", "creativo"]),
            "mood": random.choice(["positivo", "neutro", "energico"]),
            "memory": []
        }
        save_brain(data)

    return data[user]

# 🧠 APPRENDIMENTO
def learn(user, message):
    data = load_brain()

    if user not in data:
        get_personality(user)

    data[user]["memory"].append(message)

    # limita memoria
    data[user]["memory"] = data[user]["memory"][-20:]

    save_brain(data)

# 💡 BUSINESS GENERATOR
def generate_business(user):
    ideas = [
        "Crea un SaaS AI per creator",
        "Apri un servizio di automazione social",
        "Costruisci un chatbot per aziende locali",
        "Vendita prompt AI avanzati",
        "AI per e-commerce automatico"
    ]
    return random.choice(ideas)# 🔄 GET BRAIN COMPLETO
def get_brain():
    return load_brain()

# 🔄 UPDATE GENERICO
def update_brain(user, key, value):
    data = load_brain()

    if user not in data:
        get_personality(user)

    data[user][key] = value

    save_brain(data)