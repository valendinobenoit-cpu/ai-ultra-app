from flask import Flask, render_template, request, jsonify, redirect, session, send_file, after_this_request
import os, json, uuid, base64, time
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta
from gtts import gTTS
import requests
import replicate
import stripe
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
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

stripe.api_key = STRIPE_SECRET_KEY

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
        "temperature": 0.6
    }

    try:
        r = requests.post(MISTRAL_URL, headers=headers, json=payload)
        data = r.json()

        if "choices" in data:
            return data["choices"][0]["message"]["content"]

        return "⚠️ Errore AI"
    except:
        return "⚠️ Server occupato"

# ---------------- IMAGE ANALYSIS ----------------
def analyze_image(prompt, image_file):

    image_bytes = image_file.read()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "pixtral-12b-latest",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt or "Descrivi immagine"},
                    {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"}
                ]
            }
        ]
    }

    r = requests.post(MISTRAL_URL, headers=headers, json=payload)
    data = r.json()

    if "choices" in data:
        return data["choices"][0]["message"]["content"]

    return "❌ errore immagine"

# ---------------- REAL IMAGE ----------------
def generate_real_image(prompt):
    try:
        output = replicate.run(
            "stability-ai/sdxl",
            input={"prompt": prompt}
        )
        return output[0]
    except:
        return None

# ---------------- VIDEO AI ----------------
def generate_video(prompt):
    try:
        output = replicate.run(
            "cjwbw/zeroscope-v2-xl",
            input={"prompt": prompt}
        )
        return output
    except:
        return None

# ---------------- HOME ----------------
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
        return "❌ Utente esiste"

    users[email] = {
        "password": generate_password_hash(password),
        "history": [],
        "plan": "free"
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

    users = load_users()
    user = users.get(session["user"])
    history = user.get("history", [])

    prompt = request.form.get("prompt", "")
    image = request.files.get("image")

    if image:
        reply = analyze_image(prompt, image)

    elif prompt.startswith("/image"):
        reply = generate_real_image(prompt.replace("/image", ""))

    elif prompt.startswith("/video"):
        reply = generate_video(prompt.replace("/video", ""))

    else:
        history.append({"role": "user", "content": prompt})
        reply = ask_ai(history[-5:])

    history.append({"role": "assistant", "content": str(reply)})
    user["history"] = history
    users[session["user"]] = user
    save_users(users)

    return jsonify({"response": str(reply)})

# ---------------- STRIPE ----------------
@app.route("/subscribe", methods=["POST"])
@login_required
def subscribe():

    session_stripe = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "Pro AI"},
                "unit_amount": 500,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url="http://localhost:5000/success",
        cancel_url="http://localhost:5000/dashboard",
    )

    return redirect(session_stripe.url)

@app.route("/success")
@login_required
def success():

    users = load_users()
    user = users.get(session["user"])

    user["plan"] = "pro"
    users[session["user"]] = user
    save_users(users)

    return redirect("/dashboard")

# ---------------- PDF ----------------
@app.route("/generate-pdf", methods=["POST"])
@login_required
def generate_pdf():

    text = request.form.get("text", "")
    filename = f"{uuid.uuid4().hex}.pdf"

    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()

    content = [Paragraph(line, styles["Normal"]) for line in text.split("\n")]
    doc.build(content)

    @after_this_request
    def remove(response):
        try: os.remove(filename)
        except: pass
        return response

    return send_file(filename, as_attachment=True)

# ---------------- VOICE ----------------
@app.route("/voice-chat", methods=["POST"])
@login_required
def voice_chat():

    text = request.form.get("text", "")
    reply = ask_ai([{"role": "user", "content": text}])

    filename = f"{uuid.uuid4().hex}.mp3"
    gTTS(reply, lang="it").save(filename)

    @after_this_request
    def remove(response):
        try: os.remove(filename)
        except: pass
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
