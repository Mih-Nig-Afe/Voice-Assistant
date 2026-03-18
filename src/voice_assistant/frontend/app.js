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
let useServerTranscription = false;
let mediaRecorder = null;
let mediaStream = null;
let recordedChunks = [];
let fallbackStopTimer = null;
let fallbackShouldTranscribe = true;
let orbX = 0;
let orbY = 0;
let targetX = 0;
let targetY = 0;
const MAX_NETWORK_ERRORS = 3;
const SPEECH_ERROR_COOLDOWN_MS = 2500;
const MIC_NETWORK_PAUSE_MS = 10000;
const FALLBACK_RECORDING_MS = 7000;

function isLoopbackHost(hostname) {
  if (!hostname) {
    return false;
  }
  const normalized = hostname.trim().toLowerCase();
  return (
    normalized === "localhost" ||
    normalized === "::1" ||
    normalized === "[::1]" ||
    /^127(?:\.\d{1,3}){3}$/.test(normalized)
  );
}

function canUseServerTranscription() {
  return Boolean(
    window.MediaRecorder &&
      navigator.mediaDevices &&
      navigator.mediaDevices.getUserMedia
  );
}

function getIdleMicLabel() {
  return useServerTranscription ? "Start Recording" : "Start Listening";
}

function setMicButtonIdle() {
  if (!micBtn) {
    return;
  }
  micBtn.disabled = false;
  micBtn.textContent = getIdleMicLabel();
}

function getMicRuntimeContext() {
  const host = window.location?.hostname || "";
  const secure = window.isSecureContext || isLoopbackHost(host);
  const embedded = window.top !== window.self;
  const hasMediaDevices = Boolean(
    navigator.mediaDevices && navigator.mediaDevices.getUserMedia
  );
  const hasSpeechRecognition = Boolean(
    window.SpeechRecognition || window.webkitSpeechRecognition
  );
  return { secure, embedded, hasMediaDevices, hasSpeechRecognition, host };
}

function showMicGuidanceOnce(reason) {
  if (micGuidanceShown) {
    return;
  }
  micGuidanceShown = true;

  const context = getMicRuntimeContext();
  const port = window.location?.port ? `:${window.location.port}` : "";
  if (context.host === "0.0.0.0") {
    addMessage(
      "bot",
      `This page was opened on 0.0.0.0, which is only a bind address. Open http://127.0.0.1${port} or http://localhost${port} for microphone support.`
    );
    setState("idle", "Open app on 127.0.0.1 or localhost for voice.");
    return;
  }

  if (!context.secure) {
    addMessage(
      "bot",
      `Voice input needs a secure browser context. Open this app directly using http://127.0.0.1${port} or http://localhost${port} in Chrome/Edge.`
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

function pickRecordingMimeType() {
  if (!window.MediaRecorder || !window.MediaRecorder.isTypeSupported) {
    return "";
  }
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  for (const candidate of candidates) {
    if (window.MediaRecorder.isTypeSupported(candidate)) {
      return candidate;
    }
  }
  return "";
}

function audioExtensionFromMimeType(mimeType) {
  const lowered = (mimeType || "").toLowerCase();
  if (lowered.includes("ogg")) {
    return "ogg";
  }
  if (lowered.includes("mp4") || lowered.includes("m4a")) {
    return "m4a";
  }
  if (lowered.includes("wav")) {
    return "wav";
  }
  if (lowered.includes("mpeg") || lowered.includes("mp3")) {
    return "mp3";
  }
  return "webm";
}

async function blobToBase64(blob) {
  const buffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";

  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode.apply(null, Array.from(chunk));
  }
  return btoa(binary);
}

async function transcribeBlobViaBackend(blob) {
  const audioBase64 = await blobToBase64(blob);
  const mimeType = blob.type || "audio/webm";
  const fileName = `browser-mic.${audioExtensionFromMimeType(mimeType)}`;

  const response = await fetch("/api/speech/transcribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      audio_base64: audioBase64,
      mime_type: mimeType,
      file_name: fileName,
    }),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data?.detail || "Speech transcription request failed.");
  }
  return (data?.transcript || "").trim();
}

function cleanupRecorderResources() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  mediaRecorder = null;
  recordedChunks = [];
}

function stopFallbackRecording(transcribe = true) {
  fallbackShouldTranscribe = transcribe;
  if (fallbackStopTimer) {
    window.clearTimeout(fallbackStopTimer);
    fallbackStopTimer = null;
  }
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    return;
  }
  listening = false;
  cleanupRecorderResources();
  setMicButtonIdle();
}

async function startFallbackRecording() {
  if (!canUseServerTranscription()) {
    addMessage(
      "bot",
      "Fallback recording is unavailable in this browser. Please use text chat."
    );
    setState("idle", "Voice fallback is unavailable in this browser.");
    return;
  }

  const mimeType = pickRecordingMimeType();
  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  recordedChunks = [];
  fallbackShouldTranscribe = true;

  mediaRecorder = mimeType
    ? new MediaRecorder(mediaStream, { mimeType })
    : new MediaRecorder(mediaStream);

  mediaRecorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) {
      recordedChunks.push(event.data);
    }
  };

  mediaRecorder.onerror = () => {
    listening = false;
    cleanupRecorderResources();
    setMicButtonIdle();
    addMessage("bot", "Recording failed in the browser. You can still type.");
    setState("idle", "Recording failed. Use text chat or retry.");
  };

  mediaRecorder.onstop = async () => {
    const shouldTranscribe = fallbackShouldTranscribe;
    fallbackShouldTranscribe = true;
    listening = false;
    setMicButtonIdle();

    const inferredMimeType =
      recordedChunks[0]?.type || mimeType || "audio/webm";
    const blob = new Blob(recordedChunks, { type: inferredMimeType });
    cleanupRecorderResources();

    if (!shouldTranscribe) {
      setState("idle", "Tap the mic and speak naturally.");
      return;
    }
    if (!blob.size) {
      setState("idle", "No voice detected. Try speaking a bit louder.");
      return;
    }

    try {
      setState("idle", "Processing your voice...");
      const transcript = await transcribeBlobViaBackend(blob);
      if (!transcript) {
        addMessage("bot", "I could not detect clear speech. Please try again.");
        setState("idle", "No speech detected. Try again.");
        return;
      }
      networkErrorCount = 0;
      micLocked = false;
      micPausedUntil = 0;
      inputEl.value = transcript;
      sendMessage();
    } catch (error) {
      addMessage("bot", `Voice transcription failed: ${error.message}`);
      setState("idle", "Voice transcription failed. You can keep typing.");
    }
  };

  mediaRecorder.start();
  listening = true;
  if (micBtn) {
    micBtn.textContent = "Stop Recording";
  }
  setState(
    "listening",
    `Recording for up to ${Math.round(FALLBACK_RECORDING_MS / 1000)}s...`
  );
  fallbackStopTimer = window.setTimeout(() => {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
  }, FALLBACK_RECORDING_MS);
}

function switchToServerTranscription(message) {
  if (!canUseServerTranscription()) {
    return false;
  }
  const wasAlreadyEnabled = useServerTranscription;
  useServerTranscription = true;
  micLocked = false;
  micPausedUntil = 0;
  networkErrorCount = 0;
  setMicButtonIdle();
  if (hintEl) {
    hintEl.textContent = "Fallback voice capture is active.";
  }
  if (!wasAlreadyEnabled && message) {
    addMessage("bot", message);
  }
  setState("idle", "Fallback voice capture is ready.");
  return true;
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
    const switched = switchToServerTranscription(
      "Browser speech service is unavailable here. Switched to built-in recording mode."
    );
    if (!switched) {
      if (micBtn) {
        micBtn.disabled = true;
        micBtn.textContent = "Mic Unavailable";
      }
      if (hintEl) {
        hintEl.textContent = "Your browser does not support speech recognition.";
      }
    }
    return;
  }

  useServerTranscription = false;
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
    setMicButtonIdle();
    if (!document.body.classList.contains("is-speaking")) {
      setState("idle", "Tap the mic and speak naturally.");
    }
  };

  recognition.onerror = (event) => {
    const now = Date.now();
    const shouldShowError =
      event.error !== lastSpeechError ||
      now - lastSpeechErrorAt > SPEECH_ERROR_COOLDOWN_MS;

    lastSpeechError = event.error;
    lastSpeechErrorAt = now;

    if (event.error === "network") {
      networkErrorCount += 1;

      if (shouldShowError) {
        addMessage("bot", "Speech service network issue detected. Checking again...");
      }

      if (networkErrorCount >= MAX_NETWORK_ERRORS) {
        const switched = switchToServerTranscription(
          "Browser speech service kept failing. Switched to built-in recording mode."
        );
        if (switched) {
          return;
        }
        micLocked = true;
        micPausedUntil = Date.now() + MIC_NETWORK_PAUSE_MS;
        if (micBtn) {
          micBtn.disabled = false;
          micBtn.textContent = "Retry Mic";
        }
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
      setMicButtonIdle();
      addMessage(
        "bot",
        "Speech recognition was blocked by the browser. Click Request Mic Access, allow the prompt, then try Start Listening again."
      );
      showMicGuidanceOnce("not-allowed");
      setState("idle", "Speech permission is required for voice input.");
      return;
    }

    if (event.error === "service-not-allowed") {
      const switched = switchToServerTranscription(
        "Browser speech service is unavailable in this profile. Switched to built-in recording mode."
      );
      if (switched) {
        return;
      }
      setMicButtonIdle();
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
    networkErrorCount = 0;
    micLocked = false;
    micPausedUntil = 0;
    const transcript = event.results[0][0].transcript.trim();
    inputEl.value = transcript;
    sendMessage();
  };
}

async function ensureMicPermission() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
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
    addMessage(
      "bot",
      "Microphone access requires a secure context. Use localhost/127.0.0.1 or HTTPS."
    );
    showMicGuidanceOnce("insecure-context");
    setState("idle", "Open this app on localhost or HTTPS.");
    return false;
  }

  addMessage(
    "bot",
    "Microphone access was not granted. Allow it in browser site settings, then try again."
  );
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
      if (listening && useServerTranscription) {
        stopFallbackRecording(false);
      }
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
    if (!recognition && !useServerTranscription) {
      return;
    }

    if (micLocked && !useServerTranscription) {
      if (Date.now() < micPausedUntil) {
        const secondsLeft = Math.ceil((micPausedUntil - Date.now()) / 1000);
        addMessage(
          "bot",
          `Voice input is cooling down after network issues. Try again in about ${secondsLeft}s, or continue typing.`
        );
        return;
      }
      micLocked = false;
      networkErrorCount = 0;
      setMicButtonIdle();
    }

    const permissionState = await getMicPermissionState();
    micPermissionState = permissionState;
    if (permissionState === "denied") {
      const allowed = await requestMicAccess(false);
      if (!allowed) {
        setState("idle", "Trying voice capture despite denied pre-check...");
      }
    }

    if (useServerTranscription || !recognition) {
      if (listening) {
        stopFallbackRecording(true);
        return;
      }
      const hasPermission = await requestMicAccess(false);
      if (!hasPermission) {
        setState("idle", "Attempting fallback voice capture...");
      }
      try {
        await startFallbackRecording();
      } catch (error) {
        addMessage(
          "bot",
          `Could not start fallback recording: ${error?.message || "unknown browser error"}`
        );
        setState("idle", "Fallback voice start failed. Use text chat.");
      }
      return;
    }

    if (listening) {
      recognition.stop();
      return;
    }

    const hasPermission = await requestMicAccess(false);
    if (!hasPermission) {
      setState("idle", "Attempting voice capture...");
    }
    try {
      recognition.start();
    } catch (error) {
      const switched = switchToServerTranscription(
        "Could not start browser speech capture. Switched to built-in recording mode."
      );
      if (switched) {
        try {
          await startFallbackRecording();
        } catch (fallbackError) {
          addMessage(
            "bot",
            `Fallback recording also failed: ${fallbackError?.message || "unknown browser error"}`
          );
          setState("idle", "Voice start failed. Use text chat.");
        }
        return;
      }
      addMessage(
        "bot",
        `Could not start voice capture: ${error?.message || "unknown browser error"}`
      );
      setState("idle", "Voice start failed. Use text chat or retry mic.");
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
    if (listening) {
      if (useServerTranscription) {
        stopFallbackRecording(false);
      } else if (recognition) {
        recognition.stop();
      }
    }
    messagesEl.innerHTML = "";
    networkErrorCount = 0;
    micLocked = false;
    micPausedUntil = 0;
    setMicButtonIdle();
    addMessage("bot", "Conversation cleared in the UI. Ask me anything.");
  });
}

addMessage("bot", "Hi, I am Miehab. You can type or use the mic to talk with me.");
animateOrb();
initSpeechSynthesis();
initRecognition();
setMicButtonIdle();
