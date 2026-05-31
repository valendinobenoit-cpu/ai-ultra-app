// =====================================================
// FUTURA ULTRA
// =====================================================

let futuraEnabled = false;
let futuraAvatar = null;
let futuraMemory = [];

// =====================================================
// AVATAR SPEAK
// =====================================================

function futuraSpeak(text){

    window.speechSynthesis.cancel();

    const speech = new SpeechSynthesisUtterance(text);

    speech.lang = "it-IT";
    speech.rate = 1;
    speech.pitch = 1.1;

    if(futuraAvatar){
        futuraAvatar.classList.add("talking");
    }

    speech.onend = () => {

        if(futuraAvatar){
            futuraAvatar.classList.remove("talking");
        }

    };

    speechSynthesis.speak(speech);
}

// =====================================================
// MEMORY
// =====================================================

function saveMemory(text){

    futuraMemory.push(text);

    if(futuraMemory.length > 100){
        futuraMemory.shift();
    }

    localStorage.setItem(
        "futuraMemory",
        JSON.stringify(futuraMemory)
    );
}

function loadMemory(){

    const data =
        localStorage.getItem("futuraMemory");

    if(data){

        futuraMemory = JSON.parse(data);

    }

}

// =====================================================
// STATUS UPDATE
// =====================================================

function updateStatus(){

    const status =
        document.querySelector(".futura-status");

    if(!status) return;

    status.innerHTML =
        "ONLINE • " +
        new Date().toLocaleTimeString();

}

setInterval(updateStatus,1000);

// =====================================================
// PARTICLES
// =====================================================

function createParticles(){

    const overlay =
        document.querySelector(".futura-overlay");

    if(!overlay) return;

    for(let i=0;i<100;i++){

        const p =
            document.createElement("div");

        p.className = "futura-particle";

        p.style.left =
            Math.random()*100 + "%";

        p.style.animationDuration =
            (5 + Math.random()*10) + "s";

        overlay.appendChild(p);

    }

}

// =====================================================
// AVATAR
// =====================================================

function createAvatar(){

    if(document.getElementById("futura-avatar"))
        return;

    futuraAvatar =
        document.createElement("div");

    futuraAvatar.id = "futura-avatar";

    futuraAvatar.innerHTML = `
        <img src="/static/avatar.png">
    `;

    document.body.appendChild(
        futuraAvatar
    );

}

// =====================================================
// FUTURA COMMAND
// =====================================================

function futuraCommand(text){

    const cmd =
        text.toLowerCase().trim();

    if(cmd === "attiva futura"){

        activateFutura();

        add(
            "bot",
            "🚀 FUTURA ONLINE\n\nSistema avanzato attivato."
        );

        futuraSpeak(
            "Futura online. Tutti i sistemi sono operativi."
        );

        return true;
    }

    if(cmd === "disattiva futura"){

        deactivateFutura();

        add(
            "bot",
            "⚡ FUTURA OFFLINE"
        );

        return true;
    }

    return false;
}
