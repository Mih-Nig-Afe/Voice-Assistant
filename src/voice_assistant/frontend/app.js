const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const micBtn = document.getElementById("mic-btn");
const voiceBtn = document.getElementById("voice-btn");
const clearBtn = document.getElementById("clear-btn");
const stateEl = document.getElementById("assistant-state");
const hintEl = document.getElementById("orb-hint");
const orbWrap = document.getElementById("orb-wrap");

let speechEnabled = true;
let listening = false;
let recognition = null;
let currentVoice = null;
let orbX = 0;
let orbY = 0;
let targetX = 0;
let targetY = 0;

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setState(mode, hint) {
  document.body.classList.remove("is-listening", "is-speaking");
  if (mode === "listening") {
    document.body.classList.add("is-listening");
    stateEl.textContent = "Listening";
  } else if (mode === "speaking") {
    document.body.classList.add("is-speaking");
    stateEl.textContent = "Speaking";
  } else {
    stateEl.textContent = "Idle";
  }
  hintEl.textContent = hint;
}

function animateOrb() {
  const dx = targetX - orbX;
  const dy = targetY - orbY;
  orbX += dx * 0.02;
  orbY += dy * 0.02;
  orbWrap.style.transform = `translate(${orbX}px, ${orbY}px)`;

  if (Math.abs(dx) < 1 && Math.abs(dy) < 1) {
    targetX = (Math.random() - 0.5) * 20;
    targetY = (Math.random() - 0.5) * 20;
  }
  requestAnimationFrame(animateOrb);
}

function initSpeechSynthesis() {
  if (!("speechSynthesis" in window)) {
    speechEnabled = false;
    voiceBtn.disabled = true;
    voiceBtn.textContent = "Voice Replies: Unsupported";
    return;
  }

  const pickVoice = () => {
    const voices = window.speechSynthesis.getVoices();
    currentVoice =
      voices.find((v) => /en-US|en-GB/i.test(v.lang)) || voices[0] || null;
  };

  pickVoice();
  window.speechSynthesis.onvoiceschanged = pickVoice;
}

function speakText(text) {
  if (!speechEnabled || !("speechSynthesis" in window) || !text) {
    return;
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.voice = currentVoice;
  utterance.rate = 1;
  utterance.pitch = 1;
  utterance.onstart = () => setState("speaking", "Miehab is responding...");
  utterance.onend = () => setState("idle", "Tap the mic and speak naturally.");
  utterance.onerror = () => setState("idle", "Voice output had an error.");
  window.speechSynthesis.speak(utterance);
}

function initRecognition() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    micBtn.disabled = true;
    micBtn.textContent = "Mic Unavailable";
    hintEl.textContent = "Your browser does not support speech recognition.";
    return;
  }

  recognition = new Recognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    listening = true;
    micBtn.textContent = "Stop Listening";
    setState("listening", "Listening for your voice...");
  };

  recognition.onend = () => {
    listening = false;
    micBtn.textContent = "Start Listening";
    if (!document.body.classList.contains("is-speaking")) {
      setState("idle", "Tap the mic and speak naturally.");
    }
  };

  recognition.onerror = (event) => {
    addMessage("bot", `Speech recognition error: ${event.error}`);
    setState("idle", "Try the mic again or type your message.");
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript.trim();
    inputEl.value = transcript;
    sendMessage();
  };
}

async function sendMessage() {
  const message = inputEl.value.trim();
  if (!message) {
    return;
  }

  addMessage("user", message);
  inputEl.value = "";
  setState("idle", "Thinking...");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data?.detail || "Request failed");
    }

    addMessage("bot", data.response);
    speakText(data.response);

    if (data.should_exit) {
      micBtn.disabled = true;
      sendBtn.disabled = true;
      inputEl.disabled = true;
      setState("idle", "Session ended. Refresh to start again.");
    }
  } catch (error) {
    addMessage("bot", `I hit an error: ${error.message}`);
    setState("idle", "There was a backend issue. Try again.");
  }
}

sendBtn.addEventListener("click", sendMessage);
inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    sendMessage();
  }
});

micBtn.addEventListener("click", () => {
  if (!recognition) {
    return;
  }
  if (listening) {
    recognition.stop();
  } else {
    recognition.start();
  }
});

voiceBtn.addEventListener("click", () => {
  speechEnabled = !speechEnabled;
  voiceBtn.textContent = `Voice Replies: ${speechEnabled ? "On" : "Off"}`;
  if (!speechEnabled && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
    setState("idle", "Voice replies are muted.");
  }
});

clearBtn.addEventListener("click", () => {
  messagesEl.innerHTML = "";
  addMessage("bot", "Conversation cleared in the UI. Ask me anything.");
});

addMessage("bot", "Hi, I am Miehab. You can type or use the mic to talk with me.");
animateOrb();
initSpeechSynthesis();
initRecognition();
