from brain import update_brain, get_brain
from magic_features import evolve_response, system_boost

def enhance_prompt(user, prompt):
    update_brain(user, prompt)
    brain = get_brain(user)

    context = f"Interessi utente: {brain.get('interests', [])}\n"
    return context + system_boost(prompt)

def enhance_response(user, response):
    return evolve_response(response)