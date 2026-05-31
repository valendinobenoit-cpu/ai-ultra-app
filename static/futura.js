// =====================================================
// FUTURA SYSTEM
// =====================================================

let futuraEnabled = false;

// =====================================================
// CREA INTERFACCIA FUTURA
// =====================================================

function createFutura() {

    if (document.getElementById("futura")) {
        return;
    }

    const futura = document.createElement("div");

    futura.id = "futura";

    futura.innerHTML = `

    <div class="futura-overlay">

        <div class="futura-grid"></div>

        <div class="futura-scan"></div>

        <div class="futura-center">

            <div class="futura-title">
                FUTURA
            </div>

            <div class="futura-subtitle">
                AI OPERATING SYSTEM
            </div>

            <div class="futura-status">
                ONLINE
            </div>

        </div>

    </div>

    `;

    document.body.appendChild(futura);
}

// =====================================================
// ATTIVA FUTURA
// =====================================================

function activateFutura() {

    createFutura();

    const futura = document.getElementById("futura");

    futura.style.display = "block";

    futuraEnabled = true;

    document.body.classList.add("futura-active");

    console.log("FUTURA ATTIVA");
}

// =====================================================
// DISATTIVA FUTURA
// =====================================================

function deactivateFutura() {

    const futura = document.getElementById("futura");

    if (futura) {
        futura.style.display = "none";
    }

    futuraEnabled = false;

    document.body.classList.remove("futura-active");

    console.log("FUTURA DISATTIVA");
}

// =====================================================
// COMANDI CHAT
// =====================================================

function futuraCommand(text) {

    const cmd = text.toLowerCase().trim();

    // ATTIVAZIONE

    if (
        cmd === "attiva futura" ||
        cmd === "futura online" ||
        cmd === "avvia futura"
    ) {

        activateFutura();

        if (typeof add === "function") {

            add(
                "bot",
                "🚀 FUTURA ONLINE\n\nSistemi avanzati attivati."
            );

        }

        return true;
    }

    // DISATTIVAZIONE

    if (
        cmd === "disattiva futura" ||
        cmd === "futura offline"
    ) {

        deactivateFutura();

        if (typeof add === "function") {

            add(
                "bot",
                "⚡ FUTURA OFFLINE"
            );

        }

        return true;
    }

    return false;
}

// =====================================================
// AVVIO PAGINA
// =====================================================

window.addEventListener("load", () => {

    createFutura();

    deactivateFutura();

});

// =====================================================
// INTERCETTA SEND
// =====================================================

const originalSend = window.send;

window.send = async function () {

    const input = document.getElementById("input");

    if (!input) {

        if (originalSend) {
            return originalSend();
        }

        return;
    }

    const text = input.value.trim();

    if (futuraCommand(text)) {

        input.value = "";

        return;
    }

    if (originalSend) {
        return originalSend();
    }

};
