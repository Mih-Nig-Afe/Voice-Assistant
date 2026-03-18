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
let fallbackAudioContext = null;
let fallbackSourceNode = null;
let fallbackScriptNode = null;
let fallbackGainNode = null;
let fallbackSampleRate = 16000;
let fallbackPcmChunks = [];
let fallbackStopTimer = null;
let fallbackShouldTranscribe = true;
let orbX = 0;
let orbY = 0;
let targetX = 0;
let targetY = 0;
const SPEECH_ERROR_COOLDOWN_MS = 2500;
const FALLBACK_RECORDING_MS = 7000;
const PREFERRED_NEURAL_VOICE_HINTS = [
  "neural",
  "natural",
  "wavenet",
  "studio",
  "enhanced",
  "premium",
];
const PREFERRED_ENGLISH_VOICE_HINTS = [
  "aria",
  "jenny",
  "sara",
  "guy",
  "davis",
  "google us english",
  "libby",
  "zoe",
];
let speechJobToken = 0;
let activeSpeechAudio = null;
const SERVER_TTS_TEXT_LIMIT = 900;

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
  return Boolean(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

function canUseMediaRecorder() {
  return Boolean(window.MediaRecorder);
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
  if (!canUseMediaRecorder() || !window.MediaRecorder.isTypeSupported) {
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

function mergeFloat32Chunks(chunks) {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const merged = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function encodeWavBlob(samples, sampleRate) {
  const bytesPerSample = 2;
  const dataLength = samples.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataLength);
  const view = new DataView(buffer);
  let offset = 0;

  function writeAscii(text) {
    for (let i = 0; i < text.length; i += 1) {
      view.setUint8(offset, text.charCodeAt(i));
      offset += 1;
    }
  }

  writeAscii("RIFF");
  view.setUint32(offset, 36 + dataLength, true);
  offset += 4;
  writeAscii("WAVE");
  writeAscii("fmt ");
  view.setUint32(offset, 16, true);
  offset += 4;
  view.setUint16(offset, 1, true); // PCM
  offset += 2;
  view.setUint16(offset, 1, true); // mono
  offset += 2;
  view.setUint32(offset, sampleRate, true);
  offset += 4;
  view.setUint32(offset, sampleRate * bytesPerSample, true);
  offset += 4;
  view.setUint16(offset, bytesPerSample, true);
  offset += 2;
  view.setUint16(offset, 16, true);
  offset += 2;
  writeAscii("data");
  view.setUint32(offset, dataLength, true);
  offset += 4;

  for (let i = 0; i < samples.length; i += 1) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
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

function cleanupWebAudioResources() {
  if (fallbackSourceNode) {
    fallbackSourceNode.disconnect();
    fallbackSourceNode = null;
  }
  if (fallbackScriptNode) {
    fallbackScriptNode.onaudioprocess = null;
    fallbackScriptNode.disconnect();
    fallbackScriptNode = null;
  }
  if (fallbackGainNode) {
    fallbackGainNode.disconnect();
    fallbackGainNode = null;
  }
  if (fallbackAudioContext) {
    const ctx = fallbackAudioContext;
    fallbackAudioContext = null;
    ctx.close().catch(() => {});
  }
  fallbackSampleRate = 16000;
}

function cleanupRecorderResources() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  mediaRecorder = null;
  recordedChunks = [];
  fallbackPcmChunks = [];
}

async function handleRecordedBlob(blob) {
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
}

async function finalizeWebAudioRecording(transcribe = true) {
  const pcmChunks = fallbackPcmChunks.slice();
  const sampleRate = fallbackSampleRate;
  cleanupWebAudioResources();
  cleanupRecorderResources();
  listening = false;
  setMicButtonIdle();

  if (!transcribe) {
    setState("idle", "Tap the mic and speak naturally.");
    return;
  }

  if (!pcmChunks.length) {
    setState("idle", "No voice detected. Try speaking a bit louder.");
    return;
  }

  const merged = mergeFloat32Chunks(pcmChunks);
  const wavBlob = encodeWavBlob(merged, sampleRate);
  await handleRecordedBlob(wavBlob);
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
  if (fallbackAudioContext || fallbackSourceNode || fallbackScriptNode) {
    void finalizeWebAudioRecording(transcribe);
    return;
  }
  listening = false;
  cleanupWebAudioResources();
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

  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  recordedChunks = [];
  fallbackPcmChunks = [];
  fallbackShouldTranscribe = true;

  if (canUseMediaRecorder()) {
    const mimeType = pickRecordingMimeType();
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
      cleanupWebAudioResources();
      cleanupRecorderResources();
      setMicButtonIdle();
      addMessage("bot", "Recording failed in the browser. You can still type.");
      setState("idle", "Recording failed. Use text chat or retry.");
    };

    mediaRecorder.onstop = async () => {
      if (fallbackStopTimer) {
        window.clearTimeout(fallbackStopTimer);
        fallbackStopTimer = null;
      }
      const shouldTranscribe = fallbackShouldTranscribe;
      fallbackShouldTranscribe = true;
      listening = false;
      setMicButtonIdle();

      const inferredMimeType =
        recordedChunks[0]?.type || mimeType || "audio/webm";
      const blob = new Blob(recordedChunks, { type: inferredMimeType });
      cleanupWebAudioResources();
      cleanupRecorderResources();

      if (!shouldTranscribe) {
        setState("idle", "Tap the mic and speak naturally.");
        return;
      }
      await handleRecordedBlob(blob);
    };

    mediaRecorder.start();
  } else {
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) {
      cleanupRecorderResources();
      addMessage(
        "bot",
        "Voice fallback is unavailable in this browser. You can keep typing."
      );
      setState("idle", "Voice fallback is unavailable in this browser.");
      return;
    }
    fallbackAudioContext = new AudioContextCtor();
    fallbackSampleRate = fallbackAudioContext.sampleRate || 16000;
    fallbackSourceNode = fallbackAudioContext.createMediaStreamSource(mediaStream);
    fallbackScriptNode = fallbackAudioContext.createScriptProcessor(4096, 1, 1);
    fallbackGainNode = fallbackAudioContext.createGain();
    fallbackGainNode.gain.value = 0;

    fallbackScriptNode.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      fallbackPcmChunks.push(new Float32Array(input));
    };

    fallbackSourceNode.connect(fallbackScriptNode);
    fallbackScriptNode.connect(fallbackGainNode);
    fallbackGainNode.connect(fallbackAudioContext.destination);
  }

  listening = true;
  if (micBtn) {
    micBtn.textContent = "Stop Recording";
  }
  setState(
    "listening",
    `Recording for up to ${Math.round(FALLBACK_RECORDING_MS / 1000)}s...`
  );
  fallbackStopTimer = window.setTimeout(
    () => stopFallbackRecording(true),
    FALLBACK_RECORDING_MS
  );
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
  setState("idle", "Recording fallback is ready.");
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
    currentVoice = null;
    return;
  }

  const scoreVoice = (voice) => {
    let score = 0;
    const lang = (voice.lang || "").toLowerCase();
    const name = (voice.name || "").toLowerCase();
    const uri = (voice.voiceURI || "").toLowerCase();

    if (lang.startsWith("en-us")) {
      score += 60;
    } else if (lang.startsWith("en-gb")) {
      score += 55;
    } else if (lang.startsWith("en")) {
      score += 45;
    }

    if (voice.default) {
      score += 5;
    }

    for (const hint of PREFERRED_NEURAL_VOICE_HINTS) {
      if (name.includes(hint) || uri.includes(hint)) {
        score += 20;
      }
    }

    for (const hint of PREFERRED_ENGLISH_VOICE_HINTS) {
      if (name.includes(hint) || uri.includes(hint)) {
        score += 12;
      }
    }

    if (name.includes("male")) {
      score += 1;
    }
    if (name.includes("female")) {
      score += 1;
    }
    return score;
  };

  const pickBestVoice = (voices) => {
    if (!voices.length) {
      return null;
    }
    return [...voices].sort((a, b) => scoreVoice(b) - scoreVoice(a))[0] || voices[0];
  };

  const pickVoice = () => {
    const voices = window.speechSynthesis.getVoices();
    currentVoice = pickBestVoice(voices);
  };

  pickVoice();
  window.speechSynthesis.onvoiceschanged = pickVoice;
}

function normalizeSpeechText(text) {
  return (text || "")
    .replace(/[*_`#]/g, "")
    .replace(/\s+/g, " ")
    .replace(/([.!?])(?=[A-Za-z])/g, "$1 ")
    .trim();
}

function splitSpeechChunks(text, maxChars = 220) {
  if (!text) {
    return [];
  }
  const sentences = text.match(/[^.!?]+[.!?]?/g) || [text];
  const chunks = [];
  let current = "";

  for (const rawSentence of sentences) {
    const sentence = rawSentence.trim();
    if (!sentence) {
      continue;
    }
    const candidate = current ? `${current} ${sentence}` : sentence;
    if (candidate.length <= maxChars) {
      current = candidate;
      continue;
    }
    if (current) {
      chunks.push(current.trim());
    }
    if (sentence.length <= maxChars) {
      current = sentence;
      continue;
    }
    for (let i = 0; i < sentence.length; i += maxChars) {
      const piece = sentence.slice(i, i + maxChars).trim();
      if (piece) {
        chunks.push(piece);
      }
    }
    current = "";
  }

  if (current.trim()) {
    chunks.push(current.trim());
  }
  return chunks;
}

function getSpeechProsody(text, index, total) {
  const lower = (text || "").toLowerCase();
  let rate = 0.96;
  let pitch = 1.02;
  let volume = 1.0;

  if (/[!?]/.test(text)) {
    rate += 0.02;
    pitch += 0.03;
  }
  if (/sorry|unfortunately|cannot|can't|couldn't|error|failed/.test(lower)) {
    rate -= 0.05;
    pitch -= 0.03;
  }
  if (/great|awesome|nice|perfect|glad|good news|congrats|excellent/.test(lower)) {
    pitch += 0.04;
  }
  if (/joke|funny|laugh|haha/.test(lower)) {
    rate += 0.03;
    pitch += 0.05;
  }
  if (total > 1 && index > 0) {
    rate += 0.01;
  }

  return {
    rate: Math.max(0.82, Math.min(1.12, rate)),
    pitch: Math.max(0.86, Math.min(1.18, pitch)),
    volume: Math.max(0.8, Math.min(1.0, volume)),
  };
}

function cancelSpeechPlayback() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  if (activeSpeechAudio) {
    activeSpeechAudio.pause();
    activeSpeechAudio.src = "";
    activeSpeechAudio = null;
  }
}

async function requestServerSpeech(preparedText) {
  const clippedText = preparedText.slice(0, SERVER_TTS_TEXT_LIMIT);
  if (!clippedText) {
    return null;
  }
  const response = await fetch("/api/speech/synthesize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: clippedText }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    return null;
  }
  const audioBase64 = (data?.audio_base64 || "").trim();
  if (!audioBase64) {
    return null;
  }
  return {
    audioBase64,
    mimeType: (data?.mime_type || "audio/mpeg").trim(),
  };
}

async function playServerSpeechAudio(audioBase64, mimeType, token) {
  if (token !== speechJobToken || !speechEnabled) {
    return false;
  }
  const audio = new Audio(`data:${mimeType};base64,${audioBase64}`);
  activeSpeechAudio = audio;

  return new Promise((resolve) => {
    let settled = false;
    const finish = (ok) => {
      if (settled) {
        return;
      }
      settled = true;
      if (activeSpeechAudio === audio) {
        activeSpeechAudio = null;
      }
      resolve(ok);
    };

    audio.onended = () => {
      if (token === speechJobToken) {
        setState("idle", "Tap the mic and speak naturally.");
      }
      finish(true);
    };
    audio.onerror = () => {
      finish(false);
    };
    audio.play().then(() => {
      if (token === speechJobToken) {
        setState("speaking", "Miehab is responding...");
      }
    }).catch(() => {
      finish(false);
    });
  });
}

function speakBrowserChunks(chunks, token, index = 0) {
  if (token !== speechJobToken) {
    return;
  }
  if (index >= chunks.length) {
    setState("idle", "Tap the mic and speak naturally.");
    return;
  }

  const chunk = chunks[index];
  const utterance = new SpeechSynthesisUtterance(chunk);
  utterance.voice = currentVoice;
  utterance.lang = currentVoice?.lang || "en-US";
  const prosody = getSpeechProsody(chunk, index, chunks.length);
  utterance.rate = prosody.rate;
  utterance.pitch = prosody.pitch;
  utterance.volume = prosody.volume;

  utterance.onstart = () => {
    if (index === 0) {
      setState("speaking", "Miehab is responding...");
    }
  };
  utterance.onend = () => {
    speakBrowserChunks(chunks, token, index + 1);
  };
  utterance.onerror = () => {
    setState("idle", "Voice output had an error.");
  };
  window.speechSynthesis.speak(utterance);
}

async function speakText(text) {
  if (!speechEnabled || !text) {
    return;
  }

  const prepared = normalizeSpeechText(text);
  if (!prepared) {
    return;
  }

  speechJobToken += 1;
  const token = speechJobToken;
  cancelSpeechPlayback();

  try {
    const serverSpeech = await requestServerSpeech(prepared);
    if (serverSpeech && token === speechJobToken && speechEnabled) {
      const played = await playServerSpeechAudio(
        serverSpeech.audioBase64,
        serverSpeech.mimeType,
        token
      );
      if (played) {
        return;
      }
    }
  } catch (_) {
    // Fall through to browser speech synthesis.
  }

  if (!("speechSynthesis" in window) || token !== speechJobToken || !speechEnabled) {
    return;
  }

  const chunks = splitSpeechChunks(prepared);
  if (!chunks.length) {
    return;
  }
  speakBrowserChunks(chunks, token, 0);
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
      const switched = switchToServerTranscription(
        "Browser speech service is unreachable. Switched to built-in recording mode."
      );
      if (switched) {
        setState("idle", "Recording fallback is ready. Tap Start Recording.");
        return;
      }
      if (shouldShowError) {
        addMessage(
          "bot",
          "Browser speech service is unreachable in this browser session. Voice fallback is unavailable here, so please type your message."
        );
      }
      micLocked = false;
      micPausedUntil = 0;
      networkErrorCount = 0;
      setMicButtonIdle();
      setState("idle", "Voice fallback unavailable. You can still type.");
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
    void speakText(data.response);

    if (data.should_exit) {
      if (listening && useServerTranscription) {
        stopFallbackRecording(false);
      }
      speechJobToken += 1;
      cancelSpeechPlayback();
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
    if (!speechEnabled) {
      speechJobToken += 1;
      cancelSpeechPlayback();
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
    speechJobToken += 1;
    cancelSpeechPlayback();
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
