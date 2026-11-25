
import { useCallback, useEffect, useRef, useState } from "react";

const API_BASE = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws/chat";

// Processing chime
function playProcessingChime() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const ctx = new AudioCtx();

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(520, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(
      740,
      ctx.currentTime + 0.12
    );

    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(
      0.001,
      ctx.currentTime + 0.18
    );

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.18);
  } catch {}
}

function normalizeForSpeech(text) {
  return text
    .replace(/\b(\d{5})\b/g, (m) => m.split("").join(" "))
    .replace(/\bPF\s*(\d+)/gi, "Platform $1")
    .replace(/\bLKO\b/g, "Lucknow")
    .replace(/\bLJN\b/g, "Lucknow Junction")
    .replace(/\bNDLS\b/g, "New Delhi")
    .replace(/\*/g, "");
}

function scoreVoice(v) {
  const name = v.name.toLowerCase();
  const lang = v.lang.toLowerCase();
  let score = 0;

  if (lang.startsWith("en-in") || lang.startsWith("hi-in")) score += 50;
  else if (lang.startsWith("en-")) score += 10;

  if (
    name.includes("natural") ||
    name.includes("neural") ||
    name.includes("online")
  ) score += 40;

  if (
    name.includes("neerja") ||
    name.includes("swara") ||
    name.includes("prabhat")
  ) score += 30;

  if (name.includes("google")) score += 25;

  return score;
}

export function useKioskSocket() {
  const [appState, setAppState] = useState("idle");
  const [animation, setAnimation] = useState("idle");

  const [board, setBoard] = useState({
    station: "Lucknow Station",
    arrivals: [],
    departures: [],
  });

  const [liveTrain, setLiveTrain] = useState(null);
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState(
    "Click Speak or type any train name or number."
  );
  const [latencyMs, setLatencyMs] = useState(null);
  const [connected, setConnected] = useState(false);
  const [voices, setVoices] = useState([]);
  const [selectedVoiceURI, setSelectedVoiceURI] = useState("");

  const wsRef = useRef(null);
  const recognitionRef = useRef(null);
  const watchdogRef = useRef(null);
  const reconnectRef = useRef(null);
  const voicesRef = useRef([]);
  const selectedVoiceRef = useRef("");

  useEffect(() => {
    if (!("speechSynthesis" in window)) return;

    const loadVoices = () => {
      const list = window.speechSynthesis
        .getVoices()
        .filter(
          (v) =>
            v.lang.toLowerCase().startsWith("en") ||
            v.lang.toLowerCase().startsWith("hi")
        )
        .sort((a, b) => scoreVoice(b) - scoreVoice(a));

      voicesRef.current = list;
      setVoices(list);

      if (!selectedVoiceRef.current && list.length > 0) {
        selectedVoiceRef.current = list[0].voiceURI;
        setSelectedVoiceURI(list[0].voiceURI);
      }
    };

    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;

    return () => {
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, []);

  const selectVoice = useCallback((uri) => {
    selectedVoiceRef.current = uri;
    setSelectedVoiceURI(uri);
  }, []);

  const clearWatchdog = useCallback(() => {
    if (watchdogRef.current) {
      clearTimeout(watchdogRef.current);
      watchdogRef.current = null;
    }
  }, []);

  const startWatchdog = useCallback(() => {
    clearWatchdog();

    watchdogRef.current = setTimeout(() => {
      setAppState("error");
      setAnimation("idle");
      setReply("Server took too long to respond. Please try again.");
    }, 28000);
  }, [clearWatchdog]);

  const fetchBoard = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/board`);

      if (res.ok) {
        setBoard(await res.json());
      }
    } catch {
      setAppState("error");
    }
  }, []);

  const speakReply = useCallback((text, targetAnim) => {
    setAppState("speaking");
    setAnimation(targetAnim || "talk");

    const finish = () => {
      setAppState("idle");
      setAnimation("idle");
    };

    if ("speechSynthesis" in window && text) {
      window.speechSynthesis.cancel();

      const utter = new SpeechSynthesisUtterance(
        normalizeForSpeech(text)
      );

      const chosen = voicesRef.current.find(
        (v) => v.voiceURI === selectedVoiceRef.current
      );

      if (chosen) {
        utter.voice = chosen;
        utter.lang = chosen.lang;
      } else {
        utter.lang = "en-IN";
      }

      utter.rate = 0.98;
      utter.pitch = 1.0;
      utter.onend = finish;
      utter.onerror = finish;

      window.speechSynthesis.speak(utter);
      return;
    }

    setTimeout(finish, 2500);
  }, []);

  const previewVoice = useCallback(() => {
    speakReply(
      "Namaste! Train 12919 Malwa Express abhi Lucknow ke paas hai aur PF 1 par on time aa rahi hai.",
      "talk"
    );
  }, [speakReply]);

  const applyResponse = useCallback(
    (msg) => {
      clearWatchdog();

      setTranscript(msg.transcript || "");
      setReply(msg.reply || "");
      setLiveTrain(msg.liveTrain || null);
      setLatencyMs(msg.latencyMs ?? null);

      speakReply(msg.reply, msg.animation);
    },
    [clearWatchdog, speakReply]
  );

  useEffect(() => {
    fetchBoard();

    let active = true;

    const connect = () => {
      if (!active) return;

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!active) return;
        setConnected(true);
      };

      ws.onclose = () => {
        if (!active) return;

        clearWatchdog();
        setConnected(false);

        setAppState((prev) =>
          prev === "processing" ? "error" : prev
        );

        reconnectRef.current = setTimeout(connect, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        if (msg.type === "state") {
          setAppState(msg.state);

          if (msg.state === "processing") {
            setAnimation("idle");
          }
        } else if (msg.type === "response") {
          applyResponse(msg);
        }
      };
    };

    connect();

    return () => {
      active = false;

      clearWatchdog();

      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current);
      }

      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [fetchBoard, applyResponse, clearWatchdog]);

  const sendTextQuery = useCallback(
    async (text) => {
      const trimmed = text.trim();

      if (!trimmed) return;

      // Stop any previous speech immediately.
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }

      // Play processing confirmation chime.
      playProcessingChime();

      setTranscript(trimmed);
      setAppState("processing");
      setAnimation("idle");

      startWatchdog();

      if (
        wsRef.current &&
        wsRef.current.readyState === WebSocket.OPEN
      ) {
        wsRef.current.send(
          JSON.stringify({ text: trimmed })
        );
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/api/query`, {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            text: trimmed,
          }),
        });

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        applyResponse(await res.json());
      } catch {
        clearWatchdog();

        setAppState("error");

        setReply(
          "Backend is unreachable. Ensure uvicorn is running on port 8000."
        );
      }
    },
    [applyResponse, clearWatchdog, startWatchdog]
  );

  const toggleVoice = useCallback(() => {
    const SpeechRec =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    if (!SpeechRec) {
      setAppState("error");
      setReply(
        "Voice recognition requires Chrome or Edge. You can still type below."
      );
      return;
    }

    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
      setAppState("idle");
      return;
    }

    const rec = new SpeechRec();

    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.maxAlternatives = 1;

    rec.onstart = () => {
      setAppState("listening");
      setAnimation("idle");
    };

    rec.onresult = (event) => {
      const spoken = event.results[0][0].transcript;

      setTranscript(spoken);
      sendTextQuery(spoken);
    };

    rec.onerror = () => {
      setAppState("error");

      setReply(
        "Could not capture speech. Please try again or type your query."
      );
    };

    rec.onend = () => {
      recognitionRef.current = null;
    };

    recognitionRef.current = rec;
    rec.start();
  }, [sendTextQuery]);

  return {
    appState,
    animation,
    setAnimation,
    board,
    liveTrain,
    transcript,
    reply,
    latencyMs,
    connected,
    voices,
    selectedVoiceURI,
    selectVoice,
    previewVoice,
    sendTextQuery,
    toggleVoice,
  };
}
