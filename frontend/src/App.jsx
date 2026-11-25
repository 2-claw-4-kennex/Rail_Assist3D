import React from "react";
import AvatarCanvas from "./components/AvatarCanvas";
import ControlsBar from "./components/ControlsBar";
import StationBoard from "./components/StationBoard";
import { useKioskSocket } from "./hooks/useKioskSocket";

export default function App() {
  const {
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
  } = useKioskSocket();

  return (
    <main className="kiosk-layout">
      <section className="left-pane">
        <AvatarCanvas animation={animation} appState={appState} />
        <ControlsBar
          appState={appState}
          animation={animation}
          setAnimation={setAnimation}
          transcript={transcript}
          reply={reply}
          latencyMs={latencyMs}
          connected={connected}
          voices={voices}
          selectedVoiceURI={selectedVoiceURI}
          onSelectVoice={selectVoice}
          onPreviewVoice={previewVoice}
          onSendText={sendTextQuery}
          onToggleVoice={toggleVoice}
        />
      </section>

      <StationBoard
        board={board}
        liveTrain={liveTrain}
        onSelectTrain={(num) => sendTextQuery(`Live status of train ${num}`)}
      />
    </main>
  );
}