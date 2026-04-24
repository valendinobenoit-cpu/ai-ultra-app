from flask import Flask, render_template, request, jsonify, redirect, session, send_file, after_this_request
import os, json, base64, uuid
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta
from gtts import gTTS
import google.generativeai as genai

# ---------------- INIT ----------------
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=6)
)

# GOOGLE API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

ADMIN_CODE = os.getenv("ADMIN_CODE", "1234")
USERS_FILE = "users.json"

print("===== DEBUG AVVIO =====")
print("GOOGLE API KEY:", GOOGLE_API_KEY)
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
        return {"role": "admin", "messages": 0}
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

    if not GOOGLE_API_KEY:
        return jsonify({"response": "❌ API key Google non configurata"})

    users = load_users()

    if "admin" in session:
        user_data = {"messages": 0, "history": []}
    else:
        user_data = users.get(session.get("user"))

        if not user_data:
            return jsonify({"response": "❌ Utente non trovato"})

        if "history" not in user_data:
            user_data["history"] = []

    prompt = request.form.get("prompt", "")
    image_file = request.files.get("image")

    if not prompt and not image_file:
        return jsonify({"response": "❌ Scrivi qualcosa o carica un'immagine"})

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        # 🖼️ IMMAGINE
        if image_file:
            image_bytes = image_file.read()

            response = model.generate_content([
                prompt if prompt else "Descrivi questa immagine",
                {
                    "mime_type": image_file.mimetype,
                    "data": image_bytes
                }
            ])
        else:
            response = model.generate_content(prompt)

        reply = response.text

        # SALVA STORIA
        user_data["history"].append({"role": "user", "content": prompt})
        user_data["history"].append({"role": "assistant", "content": reply})

        if "admin" not in session:
            user_data["messages"] += 1
            users[session["user"]] = user_data
            save_users(users)

        return jsonify({"response": reply})

    except Exception as e:
        print("ERRORE:", str(e))
        return jsonify({"response": f"❌ Errore server: {str(e)}"})

# ---------------- VOICE CHAT ----------------
@app.route("/voice-chat", methods=["POST"])
@login_required
def voice_chat():
    if not GOOGLE_API_KEY:
        return "❌ API key non configurata", 500

    text = request.form.get("text", "")
    if not text:
        return "❌ Nessun testo", 400

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(text)

        reply = response.text

        filename = f"audio_{uuid.uuid4().hex}.mp3"
        gTTS(reply, lang="it").save(filename)

        @after_this_request
        def remove_file(response):
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except:
                pass
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
