from flask import Flask, render_template, request, jsonify, redirect, session, send_file, after_this_request
import os, json, uuid, time, requests
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta
from gtts import gTTS

# ================= INIT =================
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=6)
)

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

USERS_FILE = "users.json"
PLUGINS_FILE = "plugins.json"


# ================= UTIL: DATABASE =================
def load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return {}

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


# ================= MEMORY SYSTEM (EVOLVED) =================
class MemoryEngine:
    """Memoria intelligente per utenti"""
    
    def __init__(self):
        self.users = load_json(USERS_FILE)

    def get(self, user):
        return self.users.get(user, {
            "password": "",
            "messages": 0,
            "history": [],
            "profile": {},
            "preferences": {},
            "projects": {}
        })

    def save(self):
        save_json(USERS_FILE, self.users)

    def add_message(self, user, role, content):
        u = self.get(user)
        u["history"].append({"role": role, "content": content})

        # memory trimming (compressione contesto)
        if len(u["history"]) > 30:
            u["history"] = u["history"][-30:]

        self.users[user] = u
        self.save()


memory = MemoryEngine()


# ================= PLUGIN SYSTEM =================
class PluginSystem:
    """Sistema per aggiungere abilità modulari"""

    def __init__(self):
        self.plugins = {
            "code": True,
            "vision": True,
            "voice": True,
            "files": True,
            "web": True,
            "automation": True,
            "creative": True
        }

    def run(self, name, data):
        if not self.plugins.get(name):
            return None
        return f"[PLUGIN:{name}] processed"


plugins = PluginSystem()


# ================= AUTH =================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session and "admin" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return wrapper


# ================= AI CORE (MULTI-ABILITY ENGINE) =================
def ask_ai(messages, mode="smart"):

    system = {
        "role": "system",
        "content": """
Sei un AI avanzata modulare con abilità estese:

ABILITÀ ATTIVE:
- programmazione avanzata
- debugging
- creazione app
- analisi file
- creatività
- ragionamento logico
- sintesi intelligente
- supporto tecnico
- generazione idee
- automazione task

REGOLE:
- risposte concise ma potenti
- usa ragionamento quando serve
- se richiesta complessa, spezzala in step
"""
    }

    payload = {
        "model": "mistral-small-latest",
        "messages": [system] + messages,
        "temperature": 0.7
    }

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    for _ in range(3):
        try:
            r = requests.post(MISTRAL_URL, headers=headers, json=payload)
            data = r.json()

            if "choices" in data:
                return data["choices"][0]["message"]["content"]

        except Exception:
            time.sleep(1)

    return "⚠️ AI momentaneamente non disponibile"


# ================= ROUTES =================

@app.route("/")
def home():
    if "user" in session or "admin" in session:
        return redirect("/dashboard")
    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


# ================= CHAT ENGINE (ULTIMATE) =================
@app.route("/chat", methods=["POST"])
@login_required
def chat():

    user_id = session.get("user")
    admin = "admin" in session

    prompt = request.form.get("prompt", "")

    if not prompt:
        return jsonify({"response": "Scrivi qualcosa"})

    # MEMORY
    if not admin:
        memory.add_message(user_id, "user", prompt)
        history = memory.get(user_id)["history"]
    else:
        history = []

    # TOOL LAYER (ABILITÀ FUTURE)
    if "code" in prompt.lower():
        plugins.run("code", prompt)

    if "file" in prompt.lower():
        plugins.run("files", prompt)

    if "idea" in prompt.lower():
        plugins.run("creative", prompt)

    messages = history[-10:]

    reply = ask_ai(messages)

    if not admin:
        memory.add_message(user_id, "assistant", reply)
        memory.users[user_id]["messages"] += 1
        memory.save()

    return jsonify({"response": reply})


# ================= VOICE =================
@app.route("/voice", methods=["POST"])
@login_required
def voice():

    text = request.form.get("text", "")

    reply = ask_ai([{"role": "user", "content": text}])

    filename = f"{uuid.uuid4().hex}.mp3"
    gTTS(reply, lang="it").save(filename)

    @after_this_request
    def cleanup(response):
        if os.path.exists(filename):
            os.remove(filename)
        return response

    return send_file(filename, mimetype="audio/mpeg")


# ================= EXTENSIONS READY (ABILITÀ FUTURE) =================
"""
QUI si agganciano tutte le 100 abilità:

✔ Web scraping module
✔ Vision AI module
✔ OCR module
✔ File analyzer
✔ PDF reader
✔ Excel analyzer
✔ Code interpreter
✔ Multi-agent system
✔ Automation engine
✔ Scheduler
✔ API tools
✔ Memory compression AI
✔ Search engine integration
✔ Voice cloning
✔ Emotion AI
✔ Personal assistant mode
✔ SaaS multi-user scaling
"""


# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)
