import React from "react";

function TrainRow({ train, onSelect }) {
  return (
    <div className="train-row" onClick={() => onSelect(train.number)}>
      <span className="train-no">{train.number}</span>
      <div className="train-meta">
        <div className="train-name">{train.name}</div>
        <div className="train-route">{train.route}</div>
      </div>
      <span className="pf-badge">{train.platform}</span>
      <span className={train.delayed ? "status-delayed" : "status-ontime"}>{train.status}</span>
    </div>
  );
}

export default function StationBoard({ board, liveTrain, onSelectTrain }) {
  return (
    <aside className="board-panel">
      {liveTrain && (
        <section className="live-card">
          <div className="live-header">
            <span className="live-dot" />
            <strong>LIVE RAILRADAR TELEMETRY</strong>
          </div>
          <div className="live-title">
            {liveTrain.trainNumber} {liveTrain.trainName}
          </div>
          <div className="live-grid">
            <div>
              <span className="label">Status</span>
              <div>{liveTrain.status || "Running"}</div>
            </div>
            <div>
              <span className="label">Delay</span>
              <div>
                {liveTrain.delayMinutes !== null && liveTrain.delayMinutes !== undefined
                  ? `${liveTrain.delayMinutes} min`
                  : "On time"}
              </div>
            </div>
            <div>
              <span className="label">Current / Next</span>
              <div>
                {liveTrain.currentLocation?.stationName ||
                  liveTrain.nextStation?.stationName ||
                  liveTrain.nextStation?.stationCode ||
                  "In transit"}
              </div>
            </div>
            <div>
              <span className="label">Platform</span>
              <div>{liveTrain.platform || "-"}</div>
            </div>
          </div>
        </section>
      )}

      <h2 className="board-heading">All Trains</h2>

      <section className="board-section">
        <h3>Arrivals</h3>
        <p className="board-sub">Lucknow Station Board (click any train for live RailRadar status)</p>
        {board.arrivals.map((t) => (
          <TrainRow key={t.number} train={t} onSelect={onSelectTrain} />
        ))}
      </section>

      <section className="board-section">
        <h3>Departures</h3>
        <p className="board-sub">Top departures from Lucknow Station</p>
        {board.departures.map((t) => (
          <TrainRow key={t.number} train={t} onSelect={onSelectTrain} />
        ))}
      </section>
    </aside>
  );
}
