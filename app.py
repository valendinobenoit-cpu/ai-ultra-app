from flask import Flask, render_template, request, jsonify, redirect, session, send_file, after_this_request
import requests, os, json, base64
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

# 🔥 DEBUG AVVIO
print("===== DEBUG AVVIO =====")
print("API KEY:", GROQ_API_KEY)
print("=======================")

# ---------------- DATABASE ----------------
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

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

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    if "user" in session or "admin" in session:
        return redirect("/dashboard")
    return render_template("login.html")

@app.route("/register-page")
def register_page():
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def register():
    users = load_users()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if not email or not password:
        return "❌ Compila tutti i campi"
    if email in users:
        return "❌ Utente già esistente"

    users[email] = {
        "password": generate_password_hash(password),
        "messages": 0,
        "history": []
    }

    save_users(users)
    return redirect("/")

@app.route("/login", methods=["POST"])
def login():
    users = load_users()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if email in users and check_password_hash(users[email]["password"], password):
        session.clear()
        session["user"] = email
        session.permanent = True
        return redirect("/dashboard")

    return "❌ Login fallito"

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=get_user())

# ---------------- CHAT ----------------
@app.route("/chat", methods=["POST"])
@login_required
def chat():
    print(">>> richiesta arrivata")

    if not GROQ_API_KEY:
        return jsonify({"response": "❌ API key non configurata"})

    users = load_users()

    # 🔥 DEBUG SESSION
    print("SESSION USER:", session.get("user"))
    print("USERS:", users)

    # ADMIN
    if "admin" in session:
        user_data = {"messages": 0, "history": []}

    else:
        user_data = users.get(session.get("user"))

        # 🔴 FIX CRITICO
        if not user_data:
            return jsonify({"response": "❌ Utente non trovato"})

        if "history" not in user_data:
            user_data["history"] = []

    prompt = request.form.get("prompt", "")
    image_file = request.files.get("image")
    image_b64 = None

    if image_file:
        image_b64 = base64.b64encode(image_file.read()).decode("utf-8")

    if not prompt and not image_b64:
        return jsonify({"response": "❌ Scrivi qualcosa o carica un'immagine"})

    # MODEL
    model = "llama-3.2-11b-vision-preview" if image_b64 else "llama-3.1-8b-instant"

    # MESSAGGIO
    if image_b64:
        new_msg = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt or "Analizza questa immagine"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ]
        }
    else:
        new_msg = {"role": "user", "content": prompt}

    user_data["history"].append(new_msg)

    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": user_data["history"][-10:]
        }

        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20
        )

        print("STATUS:", r.status_code)
        print("TEXT:", r.text[:200])

        if r.status_code != 200:
            return jsonify({"response": f"❌ HTTP {r.status_code}: {r.text}"})

        try:
            res_json = r.json()
        except:
            return jsonify({"response": "❌ Risposta non JSON dal server AI"})

        if "choices" not in res_json:
            return jsonify({"response": f"❌ Risposta strana: {res_json}"})

        message = res_json["choices"][0]["message"]

        if isinstance(message["content"], list):
            reply = "".join([p.get("text", "") for p in message["content"]])
        else:
            reply = message["content"]

        user_data["history"].append({
            "role": "assistant",
            "content": reply
        })

        if "admin" not in session:
            user_data["messages"] += 1
            users[session["user"]] = user_data
            save_users(users)

        return jsonify({"response": reply})

    except Exception as e:
        print("ERRORE:", str(e))
        return jsonify({"response": f"❌ Errore server: {str(e)}"})

# ---------------- VOICE ----------------
@app.route("/voice-chat", methods=["POST"])
@login_required
def voice_chat():
    if not GROQ_API_KEY:
        return "❌ API key non configurata", 500

    text = request.form.get("text", "")
    if not text:
        return "❌ Nessun testo", 400

    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": text}]
        }

        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20
        )

        res_json = r.json()
        reply = res_json["choices"][0]["message"]["content"]

        filename = f"audio_{uuid.uuid4().hex}.mp3"
        gTTS(reply, lang="it").save(filename)

        @after_this_request
        def remove_file(response):
            if os.path.exists(filename):
                os.remove(filename)
            return response

        return send_file(filename, mimetype="audio/mpeg")

    except Exception as e:
        return f"❌ Errore: {str(e)}", 500

# ---------------- LOGOUT ----------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
