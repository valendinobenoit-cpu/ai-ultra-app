from flask import Flask, render_template, request, jsonify, redirect, session, send_file
import requests, os, json
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta
from gtts import gTTS
import uuid

# ---------------- INIT ----------------
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=6)
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_CODE = os.getenv("ADMIN_CODE", "1234")
USERS_FILE = "users.json"

FREE_LIMIT = 20  # 💰 limite gratis

# ---------------- DATABASE ----------------
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

# ---------------- AUTH ----------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session and "admin" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return wrapper

def get_user():
    if "admin" in session:
        return {"role": "admin"}
    return load_users().get(session.get("user"))

# ---------------- HOME ----------------
@app.route("/")
def home():
    if "user" in session or "admin" in session:
        return redirect("/dashboard")
    return render_template("login.html")

# ---------------- REGISTER ----------------
@app.route("/register", methods=["POST"])
def register():
    users = load_users()

    email = request.form.get("email", "").lower()
    password = request.form.get("password", "")

    if email in users:
        return "Utente già esistente"

    users[email] = {
        "password": generate_password_hash(password),
        "messages": 0,
        "history": [],
        "style": "friendly",
        "mode": "normal",
        "memory": []
    }

    save_users(users)
    return redirect("/")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    users = load_users()

    email = request.form.get("email", "").lower()
    password = request.form.get("password", "")

    if email in users and check_password_hash(users[email]["password"], password):
        session["user"] = email
        return redirect("/dashboard")

    return "Login fallito"

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=get_user())

# ---------------- CAMBIO MODALITÀ ----------------
@app.route("/set-mode", methods=["POST"])
@login_required
def set_mode():
    users = load_users()
    mode = request.form.get("mode")

    users[session["user"]]["mode"] = mode
    save_users(users)

    return "OK"

# ---------------- CHAT ----------------
@app.route("/chat", methods=["POST"])
@login_required
def chat():
    users = load_users()

    user = users.get(session["user"])

    # 💰 LIMITI
    if user["messages"] >= FREE_LIMIT:
        return jsonify({
            "response": "💰 Hai finito i messaggi gratis. Passa a Premium per continuare."
        })

    prompt = request.form.get("prompt")

    # 🔥 MODALITÀ
    mode = user.get("mode", "normal")

    mode_prompt = {
        "normal": "Rispondi normalmente",
        "tiktok": "Sei un esperto di TikTok, dai idee virali",
        "business": "Sei un esperto di business e soldi",
        "studio": "Sei un tutor che spiega semplice",
        "fitness": "Sei un coach fitness"
    }

    # 🧠 MEMORIA BASE
    memory_text = " ".join(user.get("memory", [])[-5:])

    system_prompt = f"""
Sei una AI avanzata.
Modalità: {mode_prompt.get(mode)}

Memoria utente:
{memory_text}

Regole:
- Risposte utili e pratiche
- Linguaggio naturale
- Non troppo lunghe
"""

    history = user.get("history", [])

    messages = [{"role": "system", "content": system_prompt}]
    messages += history[-10:]
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "temperature": 0.9
    }

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload
    )

    reply = r.json()["choices"][0]["message"]["content"]

    # salva chat
    history.append({"role": "user", "content": prompt})
    history.append({"role": "assistant", "content": reply})

    user["history"] = history
    user["messages"] += 1

    # 🧠 salva memoria (semplice)
    if len(prompt) < 100:
        user["memory"].append(prompt)

    users[session["user"]] = user
    save_users(users)

    return jsonify({"response": reply})

# ---------------- VOICE ----------------
@app.route("/voice", methods=["POST"])
@login_required
def voice():
    text = request.form.get("text")

    filename = f"audio_{uuid.uuid4().hex}.mp3"
    tts = gTTS(text, lang="it")
    tts.save(filename)

    return send_file(filename, mimetype="audio/mpeg")

# ---------------- LOGOUT ----------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/")

# ---------------- START ----------------
if __name__ == "__main__":
    app.run(debug=True)
