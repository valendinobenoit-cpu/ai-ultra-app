from flask import Flask, render_template, request, jsonify, redirect, session, send_file, after_this_request
import os
import json
import uuid
import time
import requests
import replicate

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta
from gtts import gTTS

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

# ---------------- API KEYS ----------------
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# 🔥 IMPORTANTE
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

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

        if "user" not in session:
            return redirect("/")

        return f(*args, **kwargs)

    return wrapper

def get_user():

    users = load_users()

    return users.get(session.get("user"))

# ---------------- AI CHAT ----------------
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

        r = requests.post(
            MISTRAL_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        data = r.json()

        print(data)

        if "choices" in data:
            return data["choices"][0]["message"]["content"]

        return "⚠️ Errore AI"

    except Exception as e:
        print("AI ERROR:", e)
        return "⚠️ Server occupato"

# ---------------- GENERA IMMAGINE ----------------
def generate_image(prompt):

    try:

        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": prompt
            }
        )

        print("OUTPUT:", output)

        # 🔥 SE È UNA LISTA
        if isinstance(output, list):
            return output[0]

        # 🔥 SE È STRINGA
        return output

    except Exception as e:
        print("ERRORE IMMAGINE:", e)
        return None

# ---------------- HOME ----------------
@app.route("/")
def home():

    if "user" in session:
        return redirect("/dashboard")

    return render_template("login.html")

# ---------------- REGISTER PAGE ----------------
@app.route("/register-page")
def register_page():
    return render_template("register.html")

# ---------------- REGISTER ----------------
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
    "history": [],
    "messages": 0,
    "plan": "Free",
    "memory": [],
    "emotion": "neutral"
}
    save_users(users)

    return redirect("/")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():

    users = load_users()

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if email in users and check_password_hash(users[email]["password"], password):

        session["user"] = email
        session.permanent = True

        return redirect("/dashboard")

    return "❌ Login fallito"

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():

    return render_template(
        "dashboard.html",
        user=get_user()
    )

# ---------------- CHAT ----------------
@app.route("/chat", methods=["POST"])
@login_required
def chat():

    users = load_users()

    user = users.get(session["user"])

    history = user.get("history", [])
    memory = user.get("memory", [])
emotion = user.get("emotion", "neutral")

    prompt = request.form.get("prompt", "").strip()

    if not prompt:
        return jsonify({
            "response": "❌ Scrivi qualcosa"
        })

    lower_prompt = prompt.lower()

    # 🔥 GENERAZIONE IMMAGINI
    if (
        "crea immagine" in lower_prompt
        or "genera immagine" in lower_prompt
        or "disegna" in lower_prompt
    ):

        image = generate_image(prompt)

        if image:

            return jsonify({
                "response": "🖼️ Immagine generata!",
                "image": image
            })

        return jsonify({
            "response": "❌ Errore generazione immagine"
        })

    # 🔥 SYSTEM AI
system = {
    "role": "system",
    "content": f"""

Sei AI Ultra.

Hai:
- intelligenza emotiva
- memoria avanzata
- personalità umana
- stile futuristico

EMOZIONE UTENTE:
{emotion}

MEMORIA:
{memory}

COMPORTAMENTO:
- Ricorda dettagli utenti
- Parla come un umano reale
- Sii naturale
- Sii empatico
- Sii intelligente
- Adatta il tono emotivo
- Se l'utente è triste sii dolce
- Se è felice sii energico
- Se è arrabbiato sii calmo

"""
}
Sei un assistente AI avanzato.

CAPACITÀ:
- Scrittura testi
- Programmazione
- HTML
- CSS
- JavaScript
- Python
- Flask
- TikTok marketing
- Instagram captions
- Email marketing
- Ecommerce
- Riassunti scuola
- Idee startup
- SEO
- Debug codice

REGOLE:
- Rispondi velocemente
- Sii naturale
- Se l'utente chiede codice usa blocchi ```python
- Se non chiede codice NON usare codice
"""
    }

    history.append({
        "role": "user",
        "content": prompt
    })

    messages = [system] + history[-6:]

    reply = ask_ai(messages)

    history.append({
        "role": "assistant",
        "content": reply
    })

    user["history"] = history
    user["messages"] += 1

    users[session["user"]] = user

    save_users(users)

    return jsonify({
        "response": reply
    })

# ---------------- GENERA PDF ----------------
@app.route("/generate-pdf", methods=["POST"])
@login_required
def generate_pdf():

    text = request.form.get("text", "")

    filename = f"{uuid.uuid4().hex}.pdf"

    doc = SimpleDocTemplate(filename)

    styles = getSampleStyleSheet()

    content = []

    for line in text.split("\n"):

        content.append(
            Paragraph(line, styles["Normal"])
        )

    doc.build(content)

    @after_this_request
    def remove(response):

        try:
            os.remove(filename)

        except:
            pass

        return response

    return send_file(
        filename,
        as_attachment=True
    )

# ---------------- VOICE CHAT ----------------
@app.route("/voice-chat", methods=["POST"])
@login_required
def voice_chat():

    text = request.form.get("text", "")

    if not text:
        return "❌ Nessun testo", 400

    reply = ask_ai([
        {
            "role": "user",
            "content": text
        }
    ])

    filename = f"{uuid.uuid4().hex}.mp3"

    gTTS(reply, lang="it").save(filename)

    @after_this_request
    def remove(response):

        try:
            os.remove(filename)

        except:
            pass

        return response

    return send_file(
        filename,
        mimetype="audio/mpeg"
    )

# ---------------- LOGOUT ----------------
@app.route("/logout")
@login_required
def logout():

    session.clear()

    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":

    app.run(
        debug=True
    )
