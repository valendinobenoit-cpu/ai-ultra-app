from flask import Flask, render_template, request, jsonify, redirect, session, send_file, after_this_request
import os, json, uuid, time
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta
from gtts import gTTS
import requests
import replicate
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
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

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
    return load_users().get(session.get("user"))

# ---------------- AI TEXT ----------------
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
        print(e)
        return "⚠️ Server occupato"

# ---------------- GENERA IMMAGINE ----------------
def generate_image(prompt):
    try:
        output = replicate.run(
            "stability-ai/sdxl",
            input={
                "prompt": prompt,
                "width": 1024,
                "height": 1024
            }
        )
        return output[0]
    except Exception as e:
        print("ERRORE IMMAGINE:", e)
        return None

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    if "user" in session:
        return redirect("/dashboard")
    return render_template("login.html")

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

    return "❌ Login fallito"

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=get_user())

# ---------------- CHAT + AUTO IMAGE ----------------
@app.route("/chat", methods=["POST"])
@login_required
def chat():

    users = load_users()
    user = users.get(session["user"])
    history = user.get("history", [])

    prompt = request.form.get("prompt", "")

    if not prompt:
        return jsonify({"response": "❌ Scrivi qualcosa"})

    # 🔥 AUTO GENERAZIONE IMMAGINE
    if "immagine" in prompt.lower() or "crea" in prompt.lower():
        img = generate_image(prompt)

        if img:
            return jsonify({
                "response": "🖼️ Immagine generata!",
                "image": img
            })
        else:
            return jsonify({"response": "❌ Errore generazione immagine"})

    # CHAT NORMALE
    system = {
        "role": "system",
        "content": "Rispondi in modo naturale, breve e utile."
    }

    history.append({"role": "user", "content": prompt})
    messages = [system] + history[-5:]

    reply = ask_ai(messages)

    history.append({"role": "assistant", "content": reply})
    user["history"] = history
    users[session["user"]] = user
    save_users(users)

    return jsonify({"response": reply})

# ---------------- PDF ----------------
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

# ---------------- VOICE ----------------
@app.route("/voice-chat", methods=["POST"])
@login_required
def voice_chat():

    text = request.form.get("text", "")

    if not text:
        return "❌ Nessun testo", 400

    reply = ask_ai([
        {"role": "user", "content": text}
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
