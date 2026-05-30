// =====================================================
// FUTURA SYSTEM
// =====================================================

let futuraEnabled = false;

// =====================================================
// CREA INTERFACCIA
// =====================================================

function createFutura(){

if(document.getElementById("futura")){
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

</div>

</div>

`;

document.body.appendChild(futura);

}

// =====================================================
// ATTIVA
// =====================================================

function activateFutura(){

createFutura();

document
.getElementById("futura")
.style
.display = "block";

futuraEnabled = true;

}

// =====================================================
// DISATTIVA
// =====================================================

function deactivateFutura(){

const futura = document.getElementById("futura");

if(futura){

futura.style.display = "none";

}

futuraEnabled = false;

}

// =====================================================
// CONTROLLA MESSAGGI
// =====================================================

function futuraCommand(text){

const cmd = text.toLowerCase().trim();

if(cmd === "attiva futura"){

activateFutura();

add(
"bot",
"🚀 FUTURA attivata"
);

return true;

}

if(cmd === "disattiva futura"){

deactivateFutura();

add(
"bot",
"FUTURA disattivata"
);

return true;

}

return false;

}
