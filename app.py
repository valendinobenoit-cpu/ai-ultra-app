import webbrowser
import os

def execute_action(action, value=None):

    if action == "open_youtube":
        webbrowser.open("https://www.youtube.com")
        return "YouTube aperto"

    elif action == "open_google":
        webbrowser.open("https://www.google.com")
        return "Google aperto"

    elif action == "create_folder":

        if not value:
            return "Nome cartella mancante"

        os.makedirs(value, exist_ok=True)

        return f"Cartella '{value}' creata"

    return "Azione sconosciuta"
