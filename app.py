from flask import Flask, render_template, request, jsonify, redirect, session, send_file, after_this_request
import os, json, uuid, time
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta
from gtts import gTTS
import requests

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# ---------------- INIT ----------------
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=6)
)

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
USERS_FILE = "users.json"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

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
        if "user" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return wrapper

def get_user():
    return load_users().get(session.get("user"))

# ---------------- AI CORE ----------------
def ask_ai(prompt):

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "open-mistral-7b",
        "messages": [
            {"role": "system", "content": "Risposte brevi, naturali, intelligenti e utili."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        r = requests.post(MISTRAL_URL, headers=headers, json=payload)
        data = r.json()

        if "choices" in data:
            return data["choices"][0]["message"]["content"]

        return "⚠️ Errore AI"

    except:
        return "⚠️ Server occupato"

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("login.html")

# ✅ FIX REGISTRAZIONE (ERA IL TUO ERRORE)
@app.route("/register-page")
def register_page():
    return render_template("register.html")

# ---------------- REGISTER ----------------
@app.route("/register", methods=["POST"])
def register():
    users = load_users()

    email = request.form.get("email", "").lower()
    password = request.form.get("password", "")

    if not email or not password:
        return "❌ Compila tutto"

    if email in users:
        return "❌ Utente già esistente"

    users[email] = {
        "password": generate_password_hash(password),
        "messages": 0
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

    return "❌ Login fallito"

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=get_user())

# ---------------- CHAT ----------------
@app.route("/chat", methods=["POST"])
@login_required
def chat():

    prompt = request.form.get("prompt", "")

    if not prompt:
        return jsonify({"response": "Scrivi qualcosa"})

    # 🔥 AI SMART FEATURES
    if "tiktok" in prompt.lower():
        prompt = f"Crea idea TikTok + caption: {prompt}"

    elif "caption" in prompt.lower():
        prompt = f"Crea caption social breve: {prompt}"

    elif "thumbnail" in prompt.lower():
        prompt = f"Crea idea thumbnail YouTube: {prompt}"

    elif "riassunto" in prompt.lower():
        prompt = f"Fai riassunto semplice: {prompt}"

    elif "ecommerce" in prompt.lower():
        prompt = f"Crea descrizione prodotto e strategia vendita: {prompt}"

    elif "email" in prompt.lower():
        prompt = f"Scrivi email marketing professionale: {prompt}"

    elif "codice" in prompt.lower() or "python" in prompt.lower():
        prompt = f"Scrivi codice completo pronto da copiare: {prompt}"

    reply = ask_ai(prompt)

    return jsonify({"response": reply})

# ---------------- PDF ----------------
@app.route("/generate-pdf", methods=["POST"])
@login_required
def generate_pdf():

    text = request.form.get("text", "")

    filename = f"{uuid.uuid4().hex}.pdf"
    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()

    content = [Paragraph(text, styles["Normal"])]
    doc.build(content)

    @after_this_request
    def remove(response):
        try:
            os.remove(filename)
        except:
            pass
        return response

    return send_file(filename, as_attachment=True)

# ---------------- VOICE ----------------
@app.route("/voice-chat", methods=["POST"])
@login_required
def voice_chat():

    text = request.form.get("text", "")

    reply = ask_ai(text)

    filename = f"{uuid.uuid4().hex}.mp3"
    gTTS(reply, lang="it").save(filename)

    @after_this_request
    def remove(response):
        try:
            os.remove(filename)
        except:
            pass
        return response

    return send_file(filename, mimetype="audio/mpeg")

# ---------------- LOGOUT ----------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
