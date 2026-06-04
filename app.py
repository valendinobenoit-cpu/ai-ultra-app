from flask import Flask, render_template, request, jsonify, redirect, session, send_file, after_this_request
import os
import json
import uuid
import requests
import replicate

from dotenv import load_dotenv
# from actions import execute_action   # rimossa o commentata: non serve sul server remoto per aprire browser
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta
from gtts import gTTS

from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# =====================================================
# INIT
# =====================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "supersecret")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=6)
)

# =====================================================
# API KEYS
# =====================================================

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

if REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

USERS_FILE = "users.json"

# =====================================================
# PLANS
# =====================================================

PLANS = {
    "Free": {"daily_limit": 30},
    "Pro": {"daily_limit": 500},
    "Ultra": {"daily_limit": 5000},
    "Enterprise": {"daily_limit": 999999},
    "Admin": {"daily_limit": -1}
}

# =====================================================
# DATABASE
# =====================================================

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

# =====================================================
# AUTH
# =====================================================

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

# =====================================================
# AI CHAT (Mistral)
# =====================================================

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
        r = requests.post(MISTRAL_URL, headers=headers, json=payload, timeout=60)
        data = r.json()
        print("MISTRAL RESPONSE:", data)
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        return "⚠️ Errore AI"
    except Exception as e:
        print("AI ERROR:", e)
        return "⚠️ Server occupato"

# =====================================================
# IMAGE GENERATION (Replicate)
# =====================================================

def generate_image(prompt):
    try:
        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={"prompt": prompt}
        )
        print("IMAGE OUTPUT:", output)
        if isinstance(output, list) and len(output) > 0:
            return str(output[0])
        return str(output)
    except Exception as e:
        print("ERRORE IMMAGINE:", e)
        return None

# =====================================================
# ROUTES: HOME / AUTH
# =====================================================

@app.route("/")
def home():
    if "user" in session:
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
        "history": [],
        "messages": 0,
        "daily_messages": 0,
        "plan": "Free",
        "memory": [],
        "emotion": "neutral"
    }
    save_users(users)
    return redirect("/")

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

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=get_user())

# =====================================================
# CHAT
# =====================================================

@app.route("/chat", methods=["POST"])
@login_required
def chat():
    users = load_users()
    user = users.get(session["user"])
    if not user:
        return jsonify({"response": "❌ Utente non trovato"}), 400

    plan = user.get("plan", "Free")

    # controllo limite giornaliero (Admin bypass)
    if plan != "Admin":
        limit = PLANS.get(plan, {}).get("daily_limit", 0)
        if limit >= 0 and user.get("daily_messages", 0) >= limit:
            return jsonify({"response": f"❌ Hai raggiunto il limite di {limit} messaggi giornalieri."})

    # Leggi prompt
    prompt = request.form.get("prompt", "").strip()
    if not prompt:
        return jsonify({"response": "❌ Scrivi qualcosa"})

    lower_prompt = prompt.lower()

    # Incrementa contatore messaggi una sola volta per richiesta valida
    user["daily_messages"] = user.get("daily_messages", 0) + 1

    # Comandi speciali che devono restituire una URL al client
    if "apri google" in lower_prompt:
        users[session["user"]] = user
        save_users(users)
        return jsonify({"response": "🌍 Sto aprendo Google...", "url": "https://www.google.com"})

    if "apri youtube" in lower_prompt:
        users[session["user"]] = user
        save_users(users)
        return jsonify({"response": "🎥 Sto aprendo YouTube...", "url": "https://www.youtube.com"})

    # Inizializza history/memory/emotion
    history = user.get("history", [])
    memory = user.get("memory", [])
    emotion = user.get("emotion", "neutral")

    # Aggiungi messaggio utente alla history (prima della chiamata AI)
    history.append({"role": "user", "content": prompt})

    # =================================================
    # EMOTION DETECTION
    # =================================================
    sad_words = ["triste", "depresso", "male", "piango", "solo", "vuoto"]
    happy_words = ["felice", "fantastico", "bellissimo", "wow", "contento"]
    angry_words = ["odio", "arrabbiato", "nervoso", "schifo"]

    if any(x in lower_prompt for x in sad_words):
        user["emotion"] = "sad"
    elif any(x in lower_prompt for x in happy_words):
        user["emotion"] = "happy"
    elif any(x in lower_prompt for x in angry_words):
        user["emotion"] = "angry"
    else:
        user["emotion"] = "neutral"

    emotion = user["emotion"]

    # =================================================
    # IMAGE GENERATION (se richiesto)
    # =================================================
    wants_image = any(kw in lower_prompt for kw in [
        "crea immagine", "genera immagine", "disegna", "creami un'immagine"
    ])

    image_url = None
    if wants_image:
        image_url = generate_image(prompt)
        if image_url is None:
            # Non interrompiamo il flusso: rispondiamo con errore immagine ma continuiamo con la chat testuale
            # aggiorna history con eventuale messaggio di errore
            history.append({"role": "assistant", "content": "❌ Errore generazione immagine"})
            user["history"] = history
            users[session["user"]] = user
            save_users(users)
            return jsonify({"response": "❌ Errore generazione immagine"})

    # =================================================
    # MEMORY (semplice append se breve)
    # =================================================
    if len(prompt) < 120:
        memory.append(prompt)
    memory = memory[-20:]
    user["memory"] = memory

    # =================================================
    # SYSTEM PROMPT + CHIAMATA AI
    # =================================================
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
- SEO
- Startup ideas
- Debug codice
- Social media
- AI assistant
- Prompt engineering

REGOLE:
- Rispondi in modo naturale
- Sii umano
- Non sembrare robotico
- Se serve usa emoji
- Se l'utente chiede codice usa markdown
- Rispondi in italiano
"""
    }

    # Limita la history inviata all'AI (es. ultimi 6 messaggi)
    messages = [system] + history[-6:]

    reply = ask_ai(messages)

    # Aggiungi risposta AI alla history
    history.append({"role": "assistant", "content": reply})

    # Aggiorna contatori e salva
    user["history"] = history
    user["messages"] = user.get("messages", 0) + 1
    users[session["user"]] = user
    save_users(users)

    # Costruisci risposta JSON: testo + eventuale immagine
    response_payload = {"response": reply}
    if image_url:
        response_payload["image"] = image_url

    return jsonify(response_payload)

# =====================================================
# PDF GENERATOR
# =====================================================

@app.route("/generate-pdf", methods=["POST"])
@login_required
def generate_pdf():
    text = request.form.get("text", "")
    filename = f"{uuid.uuid4().hex}.pdf"
    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    content = []
    for line in text.split("\n"):
        content.append(Paragraph(line, styles["Normal"]))
    doc.build(content)
    @after_this_request
    def remove(response):
        try:
            os.remove(filename)
        except:
            pass
        return response
    return send_file(filename, as_attachment=True)

# =====================================================
# VOICE CHAT
# =====================================================

@app.route("/voice-chat", methods=["POST"])
@login_required
def voice_chat():
    text = request.form.get("text", "")
    if not text:
        return "❌ Nessun testo", 400
    reply = ask_ai([{"role": "user", "content": text}])
    filename = f"{uuid.uuid4().hex}.mp3"
    try:
        gTTS(reply, lang="it").save(filename)
    except Exception as e:
        print("TTS ERROR:", e)
        return "❌ Errore TTS", 500
    @after_this_request
    def remove(response):
        try:
            os.remove(filename)
        except:
            pass
        return response
    return send_file(filename, mimetype="audio/mpeg")

# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/")

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    app.run(debug=True)
