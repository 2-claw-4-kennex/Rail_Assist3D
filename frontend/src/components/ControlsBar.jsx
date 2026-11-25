
import React, { useState } from "react";

const ANIMS = [
  { id: "idle", label: "Idle" },
  { id: "talk", label: "Talk" },
  { id: "talkHands", label: "Talk + Hands" },
  { id: "dance", label: "Dance" },
];

export default function ControlsBar({
  appState,
  animation,
  setAnimation,
  transcript,
  reply,
  latencyMs,
  connected,
  voices,
  selectedVoiceURI,
  onSelectVoice,
  onPreviewVoice,
  onSendText,
  onToggleVoice,
}) {
  const [input, setInput] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSendText(input);
    setInput("");
  };

  return (
    <div className="controls-box">
      <div className="dialogue-box">
        {transcript && (
          <div className="user-line">You: {transcript}</div>
        )}

        {appState === "processing" ? (
          <div className="loading-notif">
            <span className="spinner" />
            <span>Checking live RailRadar telemetry...</span>
          </div>
        ) : (
          <div className="bot-line">{reply}</div>
        )}

        <div className="meta-line">
          <span>WS: {connected ? "Connected" : "Offline"}</span>

          {latencyMs !== null && (
            <span>RTT: {latencyMs} ms</span>
          )}
        </div>
      </div>

      <div className="action-row">
        <button
          type="button"
          className={`mic-btn ${
            appState === "listening" ? "recording" : ""
          }`}
          onClick={onToggleVoice}
        >
          {appState === "listening" ? "Listening..." : "Speak"}
        </button>

        <form className="text-form" onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask in English or Hinglish (e.g. Where is Garib Rath?)"
          />

          <button type="submit">Ask</button>
        </form>
      </div>

      <div className="voice-row">
        <select
          className="voice-select"
          value={selectedVoiceURI}
          onChange={(e) => onSelectVoice(e.target.value)}
        >
          {voices.length === 0 && (
            <option value="">Loading browser voices...</option>
          )}

          {voices.map((v) => (
            <option key={v.voiceURI} value={v.voiceURI}>
              {v.name} ({v.lang})
            </option>
          ))}
        </select>

        <button
          type="button"
          className="anim-btn"
          onClick={onPreviewVoice}
        >
          Preview Voice
        </button>
      </div>

      <div className="anim-bar">
        {ANIMS.map((a) => (
          <button
            key={a.id}
            type="button"
            className={
              animation === a.id
                ? "anim-btn active"
                : "anim-btn"
            }
            onClick={() => setAnimation(a.id)}
          >
            {a.label}
          </button>
        ))}
      </div>
    </div>
  );
}
