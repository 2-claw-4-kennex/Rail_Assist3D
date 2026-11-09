/**
 * RailAssist 3D — Finite State Machine & Full-Duplex WebSocket Hook (Epic 3 & Epic 4)
 * Connects `playSpeechResponse` so the kiosk speaks in a clear human voice (via Browser Neural
 * SpeechSynthesis `hi-IN` / `en-IN` or Piper WAV) and animates the 3D avatar's jaw at 60 FPS.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

export const KIOSK_STATES = {
  IDLE: 'IDLE',
  LISTENING: 'LISTENING',
  PROCESSING: 'PROCESSING',
  SPEAKING: 'SPEAKING',
  ERROR: 'ERROR',
};

const WS_URL =
  import.meta.env.VITE_WS_URL ||
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:8000/ws/chat`;

const API_BASE =
  import.meta.env.VITE_API_BASE || `http://${window.location.hostname}:8000`;

export function useKioskStateMachine({ playSpeechResponse, ensureAudioContext }) {
  const [kioskState, setKioskState] = useState(KIOSK_STATES.IDLE);
  const [wsConnected, setWsConnected] = useState(false);
  const [livePreviewText, setLivePreviewText] = useState('');
  const [boardData, setBoardData] = useState({
    station_code: 'LKO',
    station_name: 'Lucknow Charbagh (LKO / LJN)',
    last_updated: new Date().toISOString(),
    trains: [],
  });
  const [kpis, setKpis] = useState({
    cache_hit_ratio_pct: 100.0,
    avg_llm_latency_ms: 210.0,
    avg_end_to_end_rtt_ms: 480.0,
    total_queries: 0,
    vram: { used_gb: 2.18, total_gb: 8.0, within_budget: true },
  });
  const [lastInteraction, setLastInteraction] = useState({
    transcript: 'नमस्ते! बटन दबाकर अपनी ट्रेन का नाम, शहर या कोई भी सवाल पूछें।',
    spoken_text:
      'नमस्ते! लखनऊ चारबाग रेल-असिस्ट कियोस्क में आपका स्वागत है। आप किसी भी ट्रेन का नाम, जैसे गोमती एक्सप्रेस या शताब्दी, बोलकर पूछ सकते हैं।',
    display_en:
      'Welcome! Ask by train name ("Where is Gomti Express?"), destination ("When will this train reach Delhi?"), or small talk ("How are you doing?").',
    intent: { intent: 'GENERAL_GREETING', train_number: null, train_name: null },
    train: null,
    latency: {
      stt_ms: 0,
      llm_ms: 0,
      router_ms: 0,
      tts_ms: 0,
      total_rtt_ms: 0,
      cache_hit: true,
    },
    error_code: null,
  });

  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const speechRecRef = useRef(null);
  const liveTranscriptRef = useRef('');
  const isHoldingRef = useRef(false);
  const processingWatchdogRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  const clearWatchdog = useCallback(() => {
    if (processingWatchdogRef.current) {
      clearTimeout(processingWatchdogRef.current);
      processingWatchdogRef.current = null;
    }
  }, []);

  const handleServerPayload = useCallback(
    (data) => {
      if (!data) return;
      if (data.board) {
        setBoardData(data.board);
      }
      if (data.kpis) {
        setKpis(data.kpis);
      }

      if (data.type === 'state_change' && data.state) {
        setKioskState(data.state);
        return;
      }

      if (data.type === 'kiosk_response') {
        clearWatchdog();
        setLivePreviewText('');
        setLastInteraction({
          transcript: data.transcript || '',
          spoken_text: data.spoken_text || '',
          display_en: data.display_en || '',
          intent: data.intent || {},
          train: data.train || null,
          latency: data.latency || {},
          error_code: data.error_code || null,
        });

        const nextState =
          data.state === 'ERROR' ? KIOSK_STATES.ERROR : KIOSK_STATES.SPEAKING;
        setKioskState(nextState);

        playSpeechResponse({
          base64Wav: data.audio_wav_base64,
          spokenText: data.spoken_text,
          useBrowserTts: data.use_browser_tts !== false,
        });
      }
    },
    [clearWatchdog, playSpeechResponse]
  );

  const postHttpEnquiryFallback = useCallback(
    async (queryText, simulateHttpStatus = null) => {
      try {
        const resp = await fetch(`${API_BASE}/api/query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: queryText || '',
            simulate_http_status: simulateHttpStatus,
          }),
        });
        const data = await resp.json();
        handleServerPayload(data);
      } catch (err) {
        clearWatchdog();
        setKioskState(KIOSK_STATES.ERROR);
        setLastInteraction((prev) => ({
          ...prev,
          transcript: queryText || '(Network Error)',
          spoken_text:
            'बैकएंड सर्वर से संपर्क नहीं हो पा रहा है। कृपया सुनिश्चित करें कि पोर्ट 8000 चालू है।',
          display_en:
            'Could not reach FastAPI backend on port 8000. Please verify the backend terminal window is running.',
        }));
      }
    },
    [clearWatchdog, handleServerPayload]
  );

  useEffect(() => {
    let isMounted = true;

    function connectWebSocket() {
      if (!isMounted) return;
      try {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
          if (!isMounted) return;
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const parsed = JSON.parse(event.data);
            handleServerPayload(parsed);
          } catch (err) {
            console.warn('Non-JSON WebSocket frame received:', err);
          }
        };

        ws.onclose = () => {
          if (!isMounted) return;
          setWsConnected(false);
          reconnectTimerRef.current = setTimeout(connectWebSocket, 2000);
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch (_) {
        reconnectTimerRef.current = setTimeout(connectWebSocket, 2000);
      }
    }

    connectWebSocket();

    fetch(`${API_BASE}/api/board`)
      .then((r) => r.json())
      .then((b) => {
        if (isMounted && b && b.trains) setBoardData(b);
      })
      .catch(() => {});

    return () => {
      isMounted = false;
      clearWatchdog();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [clearWatchdog, handleServerPayload]);

  const sendEnquiryQuery = useCallback(
    async (queryText, simulateHttpStatus = null) => {
      if (!queryText && simulateHttpStatus === null) return;
      ensureAudioContext();
      clearWatchdog();
      setKioskState(KIOSK_STATES.PROCESSING);

      await postHttpEnquiryFallback(queryText, simulateHttpStatus);
    },
    [clearWatchdog, ensureAudioContext, postHttpEnquiryFallback]
  );

  const startHoldToSpeak = useCallback(async () => {
    if (isHoldingRef.current) return;
    isHoldingRef.current = true;
    liveTranscriptRef.current = '';
    setLivePreviewText('');
    ensureAudioContext();
    clearWatchdog();
    setKioskState(KIOSK_STATES.LISTENING);

    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRec) {
      try {
        const rec = new SpeechRec();
        rec.lang = 'hi-IN';
        rec.continuous = true;
        rec.interimResults = true;
        rec.onresult = (event) => {
          let combined = '';
          for (let i = 0; i < event.results.length; i++) {
            combined += event.results[i][0].transcript + ' ';
          }
          const clean = combined.trim();
          if (clean) {
            liveTranscriptRef.current = clean;
            setLivePreviewText(clean);
          }
        };
        rec.onerror = () => {};
        rec.start();
        speechRecRef.current = rec;
      } catch (_) {}
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'start_listening' }));
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      if (!isHoldingRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }

      mediaStreamRef.current = stream;
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : '';
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      recorder.ondataavailable = (e) => {
        if (
          e.data &&
          e.data.size > 0 &&
          wsRef.current &&
          wsRef.current.readyState === WebSocket.OPEN
        ) {
          wsRef.current.send(e.data);
        }
      };

      recorder.start(150);
      mediaRecorderRef.current = recorder;
    } catch (micErr) {
      console.warn('Microphone access error:', micErr);
    }
  }, [clearWatchdog, ensureAudioContext]);

  const stopHoldToSpeak = useCallback(
    (optionalHintText = null) => {
      if (!isHoldingRef.current && !optionalHintText) return;
      isHoldingRef.current = false;
      setKioskState(KIOSK_STATES.PROCESSING);

      if (speechRecRef.current) {
        try {
          speechRecRef.current.stop();
        } catch (_) {}
        speechRecRef.current = null;
      }

      if (
        mediaRecorderRef.current &&
        mediaRecorderRef.current.state !== 'inactive'
      ) {
        try {
          mediaRecorderRef.current.stop();
        } catch (_) {}
        mediaRecorderRef.current = null;
      }

      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
      }

      // Wait 220ms so SpeechRecognition final `onresult` event flushes before sending
      setTimeout(() => {
        const finalHint = (
          optionalHintText ||
          liveTranscriptRef.current ||
          ''
        ).trim();

        clearWatchdog();
        processingWatchdogRef.current = setTimeout(() => {
          postHttpEnquiryFallback(finalHint, null);
        }, 2800);

        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(
            JSON.stringify({
              action: 'stop_listening',
              hint_text: finalHint || null,
            })
          );
        } else {
          postHttpEnquiryFallback(finalHint, null);
        }
      }, 220);
    },
    [clearWatchdog, postHttpEnquiryFallback]
  );

  const onAvatarFinishedSpeaking = useCallback(() => {
    setKioskState((prev) =>
      prev === KIOSK_STATES.SPEAKING || prev === KIOSK_STATES.ERROR
        ? KIOSK_STATES.IDLE
        : prev
    );
  }, []);

  return {
    kioskState,
    setKioskState,
    wsConnected,
    livePreviewText,
    boardData,
    kpis,
    lastInteraction,
    startHoldToSpeak,
    stopHoldToSpeak,
    sendEnquiryQuery,
    onAvatarFinishedSpeaking,
  };
}
