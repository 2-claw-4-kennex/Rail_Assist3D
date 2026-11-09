/**
 * RailAssist 3D — Main Kiosk Application Container
 * Integrates:
 * - Left Column: 3D Audio-Reactive Ready Player Me Avatar (`AvatarCanvas.jsx`) + Accessible HUD (`KioskHUD.jsx`)
 * - Right Column: Live 5-Minute Lucknow Arrival/Departure Board (`LiveStationBoard.jsx`) + Hardware/KPI Telemetry (`TelemetryPanel.jsx`)
 */

import React from 'react';
import AvatarCanvas from './components/AvatarCanvas.jsx';
import KioskHUD from './components/KioskHUD.jsx';
import LiveStationBoard from './components/LiveStationBoard.jsx';
import TelemetryPanel from './components/TelemetryPanel.jsx';
import { useAudioLipSync } from './hooks/useAudioLipSync.js';
import { useKioskStateMachine } from './hooks/useKioskStateMachine.js';

export default function App() {
  const {
    playSpeechResponse,
    sampleJawOpenWeight,
    ensureAudioContext,
  } = useAudioLipSync({
    onPlaybackStart: () => {},
    onPlaybackEnd: () => {
      onAvatarFinishedSpeaking();
    },
  });

  const {
    kioskState,
    wsConnected,
    livePreviewText,
    boardData,
    kpis,
    lastInteraction,
    startHoldToSpeak,
    stopHoldToSpeak,
    sendEnquiryQuery,
    onAvatarFinishedSpeaking,
  } = useKioskStateMachine({
    playSpeechResponse,
    ensureAudioContext,
  });

  return (
    <div className="kiosk-shell">
      {/* Top Indian Railways Kiosk Header */}
      <header className="kiosk-topbar">
        <div className="brand-block">
          <div className="rail-emblem">IR</div>
          <div>
            <h1>RailAssist 3D — भारतीय रेल पूछताछ कियोस्क</h1>
            <p>
              Multimodal Hinglish Conversational Enquiry • Lucknow Charbagh (LKO / LJN)
            </p>
          </div>
        </div>
        <div className="institution-badge">
          <span>Bennett University (SCSET)</span>
          <small>Owner: Aryan Sanskar Ahuja</small>
        </div>
      </header>

      {/* Main 2-Column Kiosk Grid (Epic 2) */}
      <main className="kiosk-grid">
        {/* Left Column: 3D Avatar + Voice Controls */}
        <section className="left-avatar-column">
          <AvatarCanvas
            kioskState={kioskState}
            sampleJawOpenWeight={sampleJawOpenWeight}
          />
          <KioskHUD
            kioskState={kioskState}
            livePreviewText={livePreviewText}
            lastInteraction={lastInteraction}
            onStartHold={startHoldToSpeak}
            onStopHold={stopHoldToSpeak}
            onPresetQuery={(q) => sendEnquiryQuery(q, null)}
          />
        </section>

        {/* Right Column: Live Station Board + KPI Telemetry */}
        <section className="right-data-column">
          <LiveStationBoard
            boardData={boardData}
            selectedTrainNo={lastInteraction?.train?.train_number}
            onSelectTrain={(q) => sendEnquiryQuery(q, null)}
          />
          <TelemetryPanel
            kpis={kpis}
            lastLatency={lastInteraction?.latency}
            wsConnected={wsConnected}
            onTriggerFailsafeTest={(q, status) => sendEnquiryQuery(q, status)}
          />
        </section>
      </main>
    </div>
  );
}
