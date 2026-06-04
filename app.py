import os
import json
import uuid
import requests
import replicate
from datetime import timedelta
from functools import wraps
from dotenv import load_dotenv
from gtts import gTTS
from werkzeug.security import generate_password_hash, check_password_hash

from flask import (
    Flask,
    render_template_string,
    request,
    jsonify,
    redirect,
    session,
    send_file,
    after_this_request,
    abort
)

from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# =====================================================
# CONFIGURAZIONE INIZIALE
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
# CHIAVI API E COSTANTI
# =====================================================

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

if REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

USERS_FILE = "users.json"

# =====================================================
# PIANI E LIMITI
# =====================================================

PLANS = {
    "Free": {"daily_limit": 30},
    "Pro": {"daily_limit": 500},
    "Ultra": {"daily_limit": 5000},
    "Enterprise": {"daily_limit": 999999},
    "Admin": {"daily_limit": -1}
}

# =====================================================
# UTILITÀ PER FILE UTENTI
# =====================================================

def load_users():
    """
    Carica il file users.json e ritorna un dizionario.
    Se il file non esiste o è corrotto, ritorna un dizionario vuoto.
    """
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users):
    """
    Salva il dizionario users su disco in formato JSON.
    """
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

# =====================================================
# DECORATOR AUTENTICAZIONE
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
# FUNZIONI AI E SERVIZI ESTERNI
# =====================================================

def ask_ai(messages):
    """
    Chiamata al servizio Mistral (o altro endpoint compatibile).
    messages: lista di messaggi in formato {"role": "...", "content": "..."}
    Ritorna la stringa di risposta o un messaggio di errore.
    """
    if not MISTRAL_API_KEY:
        return "⚠️ API key Mistral non configurata"

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

def generate_image(prompt):
    """
    Genera un'immagine tramite Replicate. Ritorna URL o identificatore immagine.
    Se Replicate non è configurato, ritorna None.
    """
    if not REPLICATE_API_TOKEN:
        print("Replicate token non configurato")
        return None
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
# TEMPLATE HTML MINIMI (render_template_string)
# =====================================================

# Nota: per semplicità includiamo template minimi qui. In produzione è meglio usare file separati.
LOGIN_HTML = """
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <title>Login</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 40px; }
    .container { max-width: 420px; margin: auto; }
    input { width: 100%; padding: 8px; margin: 6px 0; }
    button { padding: 8px 12px; }
    .link { margin-top: 12px; display:block; }
  </style>
</head>
<body>
  <div class="container">
    <h2>Accedi</h2>
    <form method="post" action="/login">
      <input name="email" placeholder="Email" required />
      <input name="password" type="password" placeholder="Password" required />
      <button type="submit">Login</button>
    </form>
    <a class="link" href="/register-page">Registrati</a>
  </div>
</body>
</html>
"""

REGISTER_HTML = """
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <title>Registrazione</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 40px; }
    .container { max-width: 420px; margin: auto; }
    input { width: 100%; padding: 8px; margin: 6px 0; }
    button { padding: 8px 12px; }
  </style>
</head>
<body>
  <div class="container">
    <h2>Registrati</h2>
    <form method="post" action="/register">
      <input name="email" placeholder="Email" required />
      <input name="password" type="password" placeholder="Password" required />
      <button type="submit">Registrati</button>
    </form>
    <a href="/">Torna al login</a>
  </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <title>Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    #chat { border: 1px solid #ddd; padding: 12px; height: 400px; overflow-y: auto; }
    .user { color: #0b6; margin: 6px 0; }
    .ai { color: #06b; margin: 6px 0; }
    .controls { margin-top: 12px; }
    input[type="text"] { width: 70%; padding: 8px; }
    button { padding: 8px 12px; }
    img.generated { max-width: 200px; display:block; margin-top:8px; }
  </style>
</head>
<body>
  <h2>Dashboard</h2>
  <div>
    <strong>Utente:</strong> {{ user_email }} &nbsp; | &nbsp; <a href="/logout">Logout</a>
  </div>
  <div id="chat"></div>
  <div class="controls">
    <form id="chat-form">
      <input id="prompt" name="prompt" type="text" placeholder="Scrivi un messaggio..." autocomplete="off" />
      <button type="submit">Invia</button>
    </form>
  </div>

<script>
const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const promptInput = document.getElementById("prompt");

function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = role === "user" ? "user" : "ai";
  div.innerText = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function appendImage(url) {
  const img = document.createElement("img");
  img.src = url;
  img.className = "generated";
  chat.appendChild(img);
  chat.scrollTop = chat.scrollHeight;
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const prompt = promptInput.value.trim();
  if (!prompt) return;
  appendMessage("user", prompt);
  const fd = new FormData();
  fd.append("prompt", prompt);
  fetch("/chat", { method: "POST", body: fd })
    .then(res => res.json())
    .then(data => {
      if (data.response) appendMessage("ai", data.response);
      if (data.image) appendImage(data.image);
      if (data.url) {
        // Apri la URL in una nuova scheda
        window.open(data.url, "_blank");
      }
    })
    .catch(err => {
      appendMessage("ai", "❌ Errore di rete");
      console.error(err);
    });
  promptInput.value = "";
});
</script>

</body>
</html>
"""

# =====================================================
# ROTTE DI BASE: HOME, REGISTER, LOGIN, DASHBOARD
# =====================================================

@app.route("/")
def home():
    if "user" in session:
        return redirect("/dashboard")
    return render_template_string(LOGIN_HTML)

@app.route("/register-page")
def register_page():
    return render_template_string(REGISTER_HTML)

@app.route("/register", methods=["POST"])
def register():
    users = load_users()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    if not email or not password:
        return "❌ Compila tutti i campi", 400
    if email in users:
        return "❌ Utente già esistente", 400
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
    return "❌ Login fallito", 401

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_user()
    return render_template_string(DASHBOARD_HTML, user_email=session.get("user"))

# =====================================================
# FUNZIONE PRINCIPALE CHAT
# =====================================================

@app.route("/chat", methods=["POST"])
@login_required
def chat():
    """
    Endpoint principale per la chat.
    Gestisce:
    - limiti per piano
    - comandi speciali (apri google, apri youtube)
    - rilevamento emozioni
    - generazione immagini
    - memoria locale
    - chiamata al modello AI con system prompt
    """
    users = load_users()
    user = users.get(session["user"])
    if not user:
        return jsonify({"response": "❌ Utente non trovato"}), 400

    plan = user.get("plan", "Free")

    # Controllo limite giornaliero (Admin bypass)
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

    # Comandi speciali: restituisci URL al client
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

    # Aggiungi messaggio utente alla history
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
            # Se fallisce la generazione immagine, rispondi con errore immagine
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
# GENERATORE PDF
# =====================================================

@app.route("/generate-pdf", methods=["POST"])
@login_required
def generate_pdf():
    text = request.form.get("text", "")
    if not text:
        return "❌ Nessun testo", 400
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
# VOICE CHAT (TTS)
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
# API DI SUPPORTO (es. reset contatori, info utente)
# =====================================================

@app.route("/api/reset-daily", methods=["POST"])
@login_required
def reset_daily():
    """
    Endpoint di utilità per resettare il contatore giornaliero dell'utente.
    Utile per test e amministrazione.
    """
    users = load_users()
    user = users.get(session["user"])
    if not user:
        return jsonify({"ok": False, "error": "utente non trovato"}), 400
    user["daily_messages"] = 0
    users[session["user"]] = user
    save_users(users)
    return jsonify({"ok": True})

@app.route("/api/me")
@login_required
def api_me():
    user = get_user()
    if not user:
        return jsonify({"ok": False, "error": "utente non trovato"}), 400
    safe_user = {
        "email": session.get("user"),
        "plan": user.get("plan"),
        "messages": user.get("messages", 0),
        "daily_messages": user.get("daily_messages", 0),
        "emotion": user.get("emotion", "neutral"),
        "memory_count": len(user.get("memory", []))
    }
    return jsonify({"ok": True, "user": safe_user})

# =====================================================
# HANDLER ERRORI SEMPLICI
# =====================================================

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404 - Pagina non trovata</h1>", 404

@app.errorhandler(500)
def server_error(e):
    return "<h1>500 - Errore interno</h1>", 500

# =====================================================
# UTILITÀ DI DEBUG E POPOLAMENTO UTENTI (solo dev)
# =====================================================

def ensure_admin_exists():
    """
    Crea un utente admin di default se non esiste (solo per sviluppo).
    """
    users = load_users()
    admin_email = "admin@example.com"
    if admin_email not in users:
        users[admin_email] = {
            "password": generate_password_hash("adminpass"),
            "history": [],
            "messages": 0,
            "daily_messages": 0,
            "plan": "Admin",
            "memory": [],
            "emotion": "neutral"
        }
        save_users(users)
        print("Utente admin creato:", admin_email)

# =====================================================
# AVVIO APP
# =====================================================

if __name__ == "__main__":
    # Solo in sviluppo: crea admin se necessario
    ensure_admin_exists()
    # Avvia l'app in debug per sviluppo locale
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

