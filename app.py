from flask import Flask, render_template, request, jsonify, redirect, session, send_file, after_this_request
import os, json, uuid, time
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta
from gtts import gTTS
import requests
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
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

ADMIN_CODE = os.getenv("ADMIN_CODE", "1234")
USERS_FILE = "users.json"

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

# ---------------- AI CORE ----------------
def ask_ai(messages):

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "mistral-small-latest",
        "messages": messages,
        "temperature": 0.7
    }

    try:
        r = requests.post(MISTRAL_URL, headers=headers, json=payload)
        data = r.json()

        if "choices" in data:
            return data["choices"][0]["message"]["content"]

        return "⚠️ Errore AI"

    except Exception as e:
        return f"❌ {str(e)}"

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
        return "Utente esiste"

    users[email] = {
        "password": generate_password_hash(password),
        "history": []
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

# ---------------- CHAT ----------------
@app.route("/chat", methods=["POST"])
@login_required
def chat():

    users = load_users()
    user = users.get(session["user"])
    history = user.get("history", [])

    prompt = request.form.get("prompt", "")

    if not prompt:
        return jsonify({"response": "Scrivi qualcosa"})

    # 🔥 SYSTEM INTELLIGENTE
    system = {
        "role": "system",
        "content": """
Rispondi in modo naturale, umano e breve.
Scrivi codice SOLO se l'utente lo chiede.
Se scrivi codice, usa blocchi ```.
"""
    }

    history.append({"role": "user", "content": prompt})

    messages = [system] + history[-5:]

    reply = ask_ai(messages)

    history.append({"role": "assistant", "content": reply})
    user["history"] = history
    users[session["user"]] = user
    save_users(users)

    return jsonify({"response": reply})

# ---------------- VOICE ----------------
@app.route("/voice-chat", methods=["POST"])
@login_required
def voice_chat():

    text = request.form.get("text", "")

    messages = [
        {"role": "system", "content": "Risposte brevi e naturali"},
        {"role": "user", "content": text}
    ]

    reply = ask_ai(messages)

    filename = f"audio_{uuid.uuid4().hex}.mp3"
    gTTS(reply, lang="it").save(filename)

    @after_this_request
    def remove_file(response):
        try:
            os.remove(filename)
        except:
            pass
        return response

    return send_file(filename, mimetype="audio/mpeg")

# ---------------- PDF GENERATOR ----------------
@app.route("/generate-pdf", methods=["POST"])
@login_required
def generate_pdf():

    text = request.form.get("text", "")

    filename = f"file_{uuid.uuid4().hex}.pdf"

    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()

    content = [Paragraph(text, styles["Normal"])]

    doc.build(content)

    @after_this_request
    def remove_file(response):
        try:
            os.remove(filename)
        except:
            pass
        return response

    return send_file(filename, as_attachment=True)

# ---------------- CREATOR TOOLS ----------------
@app.route("/ai-tools", methods=["POST"])
@login_required
def ai_tools():

    tool = request.form.get("tool")
    input_text = request.form.get("text")

    prompts = {
        "tiktok": f"Crea idea TikTok: {input_text}",
        "caption": f"Crea caption Instagram: {input_text}",
        "thumbnail": f"Crea idea thumbnail YouTube: {input_text}",
        "school": f"Riassumi: {input_text}",
        "email": f"Scrivi email marketing: {input_text}",
        "ecommerce": f"Descrizione prodotto: {input_text}"
    }

    prompt = prompts.get(tool, input_text)

    messages = [
        {"role": "system", "content": "Risposte brevi e utili"},
        {"role": "user", "content": prompt}
    ]

    reply = ask_ai(messages)

    return jsonify({"response": reply})

# ---------------- LOGOUT ----------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
