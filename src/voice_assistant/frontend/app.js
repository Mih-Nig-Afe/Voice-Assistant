const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const micBtn = document.getElementById("mic-btn");
const micAccessBtn = document.getElementById("mic-access-btn");
const voiceBtn = document.getElementById("voice-btn");
const clearBtn = document.getElementById("clear-btn");
const stateEl = document.getElementById("assistant-state");
const hintEl = document.getElementById("orb-hint");
const orbWrap = document.getElementById("orb-wrap");

let speechEnabled = true;
let listening = false;
let recognition = null;
let currentVoice = null;
let micLocked = false;
let networkErrorCount = 0;
let lastSpeechError = "";
let lastSpeechErrorAt = 0;
let micPausedUntil = 0;
let micPermissionState = "unknown";
let micGuidanceShown = false;
let orbX = 0;
let orbY = 0;
let targetX = 0;
let targetY = 0;
const MAX_NETWORK_ERRORS = 3;
const SPEECH_ERROR_COOLDOWN_MS = 2500;
const MIC_NETWORK_PAUSE_MS = 10000;

function getMicRuntimeContext() {
  const secure = window.isSecureContext;
  const embedded = window.top !== window.self;
  const hasMediaDevices = Boolean(
    navigator.mediaDevices && navigator.mediaDevices.getUserMedia
  );
  const hasSpeechRecognition = Boolean(
    window.SpeechRecognition || window.webkitSpeechRecognition
  );
  return { secure, embedded, hasMediaDevices, hasSpeechRecognition };
}

function showMicGuidanceOnce(reason) {
  if (micGuidanceShown) {
    return;
  }
  micGuidanceShown = true;

  const context = getMicRuntimeContext();
  if (!context.secure) {
    addMessage(
      "bot",
      "Voice input needs a secure browser context. Open this app directly using http://127.0.0.1:8000 or http://localhost:8000 in Chrome/Edge."
    );
    setState("idle", "Open app directly on localhost in Chrome/Edge.");
    return;
  }

  if (context.embedded) {
    addMessage(
      "bot",
      "Voice input is often blocked in embedded/in-app browsers. Open the same URL in a normal Chrome/Edge tab and try again."
    );
    setState("idle", "Open in normal browser tab for voice.");
    return;
  }

  if (!context.hasMediaDevices) {
    addMessage(
      "bot",
      "This browser session cannot access microphone APIs. Try latest Chrome/Edge and confirm microphone permissions are enabled."
    );
    setState("idle", "Browser session lacks microphone APIs.");
    return;
  }

  if (reason === "service-not-allowed") {
    addMessage(
      "bot",
      "Speech recognition service is blocked by this browser profile. Use latest Chrome/Edge, allow microphone, and avoid embedded preview windows."
    );
    setState("idle", "Speech service blocked by browser profile.");
  }
}

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
    if (voiceBtn) {
      voiceBtn.disabled = true;
      voiceBtn.textContent = "Voice Replies: Unsupported";
    }
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
    if (micBtn) {
      micBtn.disabled = true;
      micBtn.textContent = "Mic Unavailable";
    }
    if (hintEl) {
      hintEl.textContent = "Your browser does not support speech recognition.";
    }
    return;
  }

  recognition = new Recognition();
  recognition.lang = "en-US";
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    listening = true;
    if (micBtn) {
      micBtn.textContent = "Stop Listening";
    }
    setState("listening", "Listening for your voice...");
  };

  recognition.onend = () => {
    listening = false;
    if (micBtn) {
      micBtn.textContent = "Start Listening";
    }
    if (!document.body.classList.contains("is-speaking")) {
      setState("idle", "Tap the mic and speak naturally.");
    }
  };

  recognition.onerror = (event) => {
    const now = Date.now();
    const shouldShowError =
      event.error !== lastSpeechError || now - lastSpeechErrorAt > SPEECH_ERROR_COOLDOWN_MS;

    lastSpeechError = event.error;
    lastSpeechErrorAt = now;

    if (event.error === "network") {
      networkErrorCount += 1;

      if (shouldShowError) {
        addMessage(
          "bot",
          "Speech service network issue detected. Checking again..."
        );
      }

      if (networkErrorCount >= MAX_NETWORK_ERRORS) {
        micLocked = true;
        micPausedUntil = Date.now() + MIC_NETWORK_PAUSE_MS;
        micBtn.disabled = false;
        micBtn.textContent = "Retry Mic";
        addMessage(
          "bot",
          "Voice input paused after repeated network errors. Please check internet, then tap Retry Mic in a few seconds."
        );
        setState("idle", "Voice paused. You can still chat by typing.");
        return;
      }

      setState("idle", "Temporary speech network issue. Retrying...");
      return;
    }

    if (event.error === "not-allowed") {
      micLocked = false;
      if (micBtn) {
        micBtn.disabled = false;
        micBtn.textContent = "Start Listening";
      }
      addMessage(
        "bot",
        "Speech recognition was blocked by the browser. Click Request Mic Access, allow the prompt, then try Start Listening again."
      );
      showMicGuidanceOnce("not-allowed");
      setState("idle", "Speech permission is required for voice input.");
      return;
    }

    if (event.error === "service-not-allowed") {
      if (micBtn) {
        micBtn.disabled = false;
        micBtn.textContent = "Start Listening";
      }
      addMessage(
        "bot",
        "Speech recognition service is blocked or unavailable in this browser profile. Try Chrome/Edge and ensure microphone access is allowed."
      );
      showMicGuidanceOnce("service-not-allowed");
      setState("idle", "Speech service unavailable.");
      return;
    }

    if (shouldShowError) {
      addMessage("bot", `Speech recognition error: ${event.error}`);
    }
    setState("idle", "Try the mic again or type your message.");
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript.trim();
    inputEl.value = transcript;
    sendMessage();
  };
}

async function ensureMicPermission() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    // Some browsers can still handle SpeechRecognition without exposing getUserMedia.
    return { ok: false, reason: "preflight-unavailable" };
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    micPermissionState = "granted";
    return { ok: true, reason: "granted" };
  } catch (error) {
    if (error && error.name === "SecurityError") {
      return { ok: false, reason: "insecure-context" };
    }
    if (error && error.name === "NotAllowedError") {
      micPermissionState = "denied";
      return { ok: false, reason: "denied" };
    }
    return { ok: false, reason: "unavailable" };
  }
}

async function getMicPermissionState() {
  if (!navigator.permissions || !navigator.permissions.query) {
    return "unknown";
  }

  try {
    const result = await navigator.permissions.query({ name: "microphone" });
    return result.state;
  } catch (_) {
    return "unknown";
  }
}

async function requestMicAccess(showSuccess = true) {
  const result = await ensureMicPermission();
  if (result.ok) {
    if (showSuccess) {
      addMessage("bot", "Microphone access granted. You can start listening now.");
    }
    setState("idle", "Microphone is ready.");
    return true;
  }

  if (result.reason === "preflight-unavailable") {
    // Do not block: let SpeechRecognition attempt directly.
    if (showSuccess) {
      addMessage(
        "bot",
        "Microphone pre-check is unavailable in this browser; trying direct voice capture."
      );
    }
    setState("idle", "Trying direct microphone access...");
    showMicGuidanceOnce("preflight-unavailable");
    return true;
  }

  if (result.reason === "insecure-context") {
    addMessage("bot", "Microphone access requires a secure context. Use localhost/127.0.0.1 or HTTPS.");
    showMicGuidanceOnce("insecure-context");
    setState("idle", "Open this app on localhost or HTTPS.");
    return false;
  }

  addMessage("bot", "Microphone access was not granted. Allow it in browser site settings, then try again.");
  setState("idle", "Microphone permission is required.");
  return false;
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

if (sendBtn) {
  sendBtn.addEventListener("click", sendMessage);
}

if (inputEl) {
  inputEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      sendMessage();
    }
  });
}

if (micBtn) {
  micBtn.addEventListener("click", async () => {
  if (!recognition) {
    return;
  }

  if (micLocked) {
    if (Date.now() < micPausedUntil) {
      const secondsLeft = Math.ceil((micPausedUntil - Date.now()) / 1000);
      addMessage(
        "bot",
        `Voice input is cooling down after network issues. Try again in about ${secondsLeft}s, or continue typing.`
      );
      return;
    }
    micLocked = false;
    micBtn.disabled = false;
    micBtn.textContent = "Start Listening";
    networkErrorCount = 0;
  }

  const permissionState = await getMicPermissionState();
  micPermissionState = permissionState;
  if (permissionState === "denied") {
    // Some browsers report stale/incorrect permission states, so still attempt request.
    const allowed = await requestMicAccess(false);
    if (!allowed) {
      // Continue anyway and let recognition produce the definitive browser error.
      setState("idle", "Trying voice capture despite denied pre-check...");
    }
  }

  if (listening) {
    recognition.stop();
  } else {
    const hasPermission = await requestMicAccess(false);
    if (!hasPermission) {
      // Attempt start anyway for browsers where pre-check is unreliable.
      setState("idle", "Attempting voice capture...");
    }
    try {
      recognition.start();
    } catch (error) {
      addMessage(
        "bot",
        `Could not start voice capture: ${error?.message || "unknown browser error"}`
      );
      setState("idle", "Voice start failed. Use text chat or retry mic.");
    }
  }
  });
}

if (micAccessBtn) {
  micAccessBtn.addEventListener("click", async () => {
    await requestMicAccess(true);
  });
}

if (voiceBtn) {
  voiceBtn.addEventListener("click", () => {
    speechEnabled = !speechEnabled;
    voiceBtn.textContent = `Voice Replies: ${speechEnabled ? "On" : "Off"}`;
    if (!speechEnabled && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      setState("idle", "Voice replies are muted.");
    }
  });
}

if (clearBtn) {
  clearBtn.addEventListener("click", () => {
    messagesEl.innerHTML = "";
    networkErrorCount = 0;
    micLocked = false;
    micPausedUntil = 0;
    if (micBtn) {
      micBtn.disabled = false;
      micBtn.textContent = "Start Listening";
    }
    addMessage("bot", "Conversation cleared in the UI. Ask me anything.");
  });
}

addMessage("bot", "Hi, I am Miehab. You can type or use the mic to talk with me.");
animateOrb();
initSpeechSynthesis();
initRecognition();
