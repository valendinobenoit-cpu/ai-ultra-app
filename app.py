from flask import Flask, render_template, request, jsonify, redirect, session
import requests, os, json, base64
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta

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
ADMIN_CODE = os.getenv("ADMIN_CODE", "1234")  # 🔐 admin code
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

# ---------------- HOME ----------------
@app.route("/")
def home():
    if "user" in session or "admin" in session:
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
        "messages": 0,
        "history": []
    }

    save_users(users)
    return redirect("/")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    users = load_users()

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    admin_code = request.form.get("admin_code", "").strip()

    # 🔐 LOGIN ADMIN
    if admin_code and admin_code == ADMIN_CODE:
        session.clear()
        session["admin"] = True
        session.permanent = True
        return redirect("/dashboard")

    # 👤 LOGIN UTENTE
    if email in users and check_password_hash(users[email]["password"], password):
        session.clear()
        session["user"] = email
        session.permanent = True
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

    # 🔥 ADMIN → no salvataggio
    if "admin" in session:
        history = []
        user = {"messages": 0}
    else:
        user = users.get(session["user"])
        if not user:
            return jsonify({"response": "❌ Utente non trovato"})
        history = user.get("history", [])

    prompt = request.form.get("prompt", "")
    image = request.files.get("image")

    if not prompt and not image:
        return jsonify({"response": "❌ Scrivi qualcosa o invia immagine"})

    if prompt:
        history.append({
            "role": "user",
            "content": prompt
        })

    if image:
        img64 = base64.b64encode(image.read()).decode("utf-8")
        history.append({
            "role": "user",
            "content": [
                {"type": "text", "text": "Analizza questa immagine"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img64}"
                    }
                }
            ]
        })

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": history[-10:],
        "temperature": 0.7
    }

    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload
        )

        result = r.json()
        reply = result["choices"][0]["message"]["content"]

        history.append({
            "role": "assistant",
            "content": reply
        })

        # 🔥 salva solo utenti normali
        if "admin" not in session:
            user["history"] = history
            user["messages"] += 1
            users[session["user"]] = user
            save_users(users)

        return jsonify({"response": reply})

    except Exception as e:
        return jsonify({"response": f"❌ Errore AI: {str(e)}"})

# ---------------- RESET ----------------
@app.route("/reset")
@login_required
def reset():
    if "admin" in session:
        return redirect("/dashboard")

    users = load_users()
    users[session["user"]]["history"] = []
    save_users(users)
    return redirect("/dashboard")

# ---------------- LOGOUT ----------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/")

# ---------------- START ----------------
if __name__ == "__main__":
    app.run(debug=True)