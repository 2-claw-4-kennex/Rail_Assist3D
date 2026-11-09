/**
 * RailAssist 3D — Accessible Kiosk Control HUD (Requirements F1, F2, N3, N4)
 * Features:
 * - High-contrast State Machine Banner (IDLE, LISTENING, PROCESSING, SPEAKING, ERROR)
 * - Live voice transcript preview while holding the mic button
 * - Bilingual Spoken Response & Active Train Telemetry Card
 * - Giant "Hold to Speak" button + Quick Hinglish Voice Presets + Direct Hinglish Input Bar
 */

import React, { useState } from 'react';
import {
  Mic,
  Volume2,
  Loader2,
  AlertOctagon,
  Sparkles,
  Navigation,
  Send,
} from 'lucide-react';
import { KIOSK_STATES } from '../hooks/useKioskStateMachine.js';

const PRESET_HINGLISH_QUERIES = [
  {
    labelHi: 'शताब्दी एक्सप्रेस कब आएगी?',
    labelEn: '12004 Shatabdi Status',
    query: '12004 Shatabdi Express kab aayegi aur kis platform par aayegi?',
  },
  {
    labelHi: 'गोमती एक्सप्रेस का प्लेटफॉर्म?',
    labelEn: '12419 Gomti Platform',
    query: 'Gomti Express ka platform number kya hai?',
  },
  {
    labelHi: 'वंदे भारत कितनी लेट है?',
    labelEn: '22426 Vande Bharat Delay',
    query: '22426 Vande Bharat Express kitna late hai?',
  },
  {
    labelHi: 'पुष्पक एक्सप्रेस कोच पोजीशन',
    labelEn: '12533 Pushpak Coaches',
    query: '12533 Pushpak Express kis platform par hai aur coach position batao',
  },
];

export default function KioskHUD({
  kioskState,
  livePreviewText,
  lastInteraction,
  onStartHold,
  onStopHold,
  onPresetQuery,
}) {
  const [customQuery, setCustomQuery] = useState('');
  const train = lastInteraction?.train;
  const isListening = kioskState === KIOSK_STATES.LISTENING;
  const isProcessing = kioskState === KIOSK_STATES.PROCESSING;
  const isSpeaking = kioskState === KIOSK_STATES.SPEAKING;
  const isError = kioskState === KIOSK_STATES.ERROR;

  const handleManualSubmit = (e) => {
    e.preventDefault();
    if (!customQuery.trim()) return;
    onPresetQuery(customQuery.trim());
    setCustomQuery('');
  };

  return (
    <div className="kiosk-hud">
      {/* State Machine Status Banner (Requirement N4 Accessibility) */}
      <div className={`state-banner state-${kioskState.toLowerCase()}`}>
        <div className="state-indicator">
          {isListening && <Mic className="pulse-icon" size={22} />}
          {isProcessing && <Loader2 className="spin-icon" size={22} />}
          {isSpeaking && <Volume2 className="pulse-icon" size={22} />}
          {isError && <AlertOctagon size={22} />}
          {kioskState === KIOSK_STATES.IDLE && <Sparkles size={22} />}
          <div>
            <div className="state-title">STATE: {kioskState}</div>
            <div className="state-desc">
              {isListening &&
                (livePreviewText
                  ? `सुन रहा हूँ: "${livePreviewText}"`
                  : 'सुन रहा हूँ... बोलते रहें (Listening — Keep Holding Button)')}
              {isProcessing && 'जाँच हो रही है... (Processing via Faster-Whisper & Qwen 2.5)'}
              {isSpeaking && 'रेलअसिस्ट बोल रहा है... (Speaking via Piper TTS hi_IN)'}
              {isError && 'कृपया नीचे दिए गए ट्रेन बटन को छुएं या दोबारा बोलें'}
              {kioskState === KIOSK_STATES.IDLE &&
                'तैयार है — नीचे बटन दबाकर पूछें या किसी ट्रेन को चुनें'}
            </div>
          </div>
        </div>
      </div>

      {/* Passenger Transcript & Avatar Bilingual Response Card */}
      <div className="dialogue-card">
        <div className="transcript-row">
          <span className="dialogue-tag">यात्री (You Asked):</span>
          <p className="transcript-text">
            "{isListening && livePreviewText ? livePreviewText : lastInteraction?.transcript}"
          </p>
        </div>

        <div className="response-row">
          <span className="dialogue-tag tag-assistant">
            RailAssist 3D ({lastInteraction?.intent?.intent || 'READY'}):
          </span>
          <p className="spoken-hi-text">{lastInteraction?.spoken_text}</p>
          <p className="display-en-text">{lastInteraction?.display_en}</p>
        </div>

        {/* Highlighted Train Telemetry Card when a train entity is matched */}
        {train && (
          <div className="active-train-spotlight">
            <div className="spotlight-top">
              <div>
                <span className="spotlight-number">#{train.train_number}</span>
                <h3 className="spotlight-name">{train.train_name}</h3>
              </div>
              <div className="spotlight-platform-box">
                <span className="pf-label">PLATFORM</span>
                <span className="pf-number">{train.platform}</span>
              </div>
            </div>

            <div className="spotlight-meta">
              <span>
                <Navigation size={14} /> {train.current_location}
              </span>
              <span>
                Arr: <strong>{train.expected_arrival}</strong> | Dep:{' '}
                <strong>{train.expected_departure}</strong>
              </span>
              <span className="source-chip">{train.data_source}</span>
            </div>

            {train.coach_position && (
              <div className="coach-strip">
                <span className="coach-label">Coach Order:</span>
                <code>{train.coach_position}</code>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Requirement F1 & N4: Giant Keyboard-Free "Hold to Speak" Button */}
      <div className="hold-to-speak-zone">
        <button
          type="button"
          className={`hold-mic-btn ${isListening ? 'mic-active' : ''}`}
          onMouseDown={onStartHold}
          onMouseUp={() => onStopHold()}
          onMouseLeave={() => {
            if (isListening) onStopHold();
          }}
          onTouchStart={(e) => {
            e.preventDefault();
            onStartHold();
          }}
          onTouchEnd={(e) => {
            e.preventDefault();
            onStopHold();
          }}
        >
          <div className="mic-ring">
            <Mic size={34} />
          </div>
          <div className="mic-btn-labels">
            <span className="mic-hi">
              {isListening
                ? 'बोलते रहें... भेजने के लिए बटन छोड़ें (Release to Send)'
                : 'बोलने के लिए दबाए रखें (Hold to Speak)'}
            </span>
            <span className="mic-en">
              Press &amp; hold while speaking in Hindi/English, then release
            </span>
          </div>
        </button>

        {/* One-Tap Hinglish Kiosk Voice Simulation Chips for Fast Commuters & Demo */}
        <div className="preset-chips-section">
          <div className="preset-caption">
            Instant Touch Enquiries (या एक क्लिक में पूछने के लिए नीचे छुएं):
          </div>
          <div className="preset-chips-grid">
            {PRESET_HINGLISH_QUERIES.map((item) => (
              <button
                key={item.labelEn}
                type="button"
                className="preset-chip"
                onClick={() => onPresetQuery(item.query)}
              >
                <span className="chip-hi">{item.labelHi}</span>
                <span className="chip-en">{item.labelEn}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Direct Hinglish Input Fallback Bar (for testing without a microphone) */}
        <form className="manual-query-form" onSubmit={handleManualSubmit}>
          <input
            type="text"
            className="manual-query-input"
            placeholder="Or type any Hinglish query here (e.g. 'Vaishali Express kitna late hai?')..."
            value={customQuery}
            onChange={(e) => setCustomQuery(e.target.value)}
          />
          <button type="submit" className="manual-query-submit">
            <Send size={16} /> Ask
          </button>
        </form>
      </div>
    </div>
  );
}
