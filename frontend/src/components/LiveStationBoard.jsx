/**
 * RailAssist 3D — Live Lucknow Station Arrival/Departure Board Component (Requirement F4.1)
 * Displays the 5-minute edge-cached station board (`lucknow_board.json`) with touch-friendly
 * one-tap enquiry triggers for elderly & commuter-in-a-hurry personas.
 */

import React from 'react';
import { Train, Clock, MapPin, CheckCircle2, AlertTriangle } from 'lucide-react';

export default function LiveStationBoard({
  boardData,
  selectedTrainNo,
  onSelectTrain,
}) {
  const trains = boardData?.trains || [];

  return (
    <section className="station-board-card" aria-label="Live Station Board">
      <div className="board-header">
        <div className="board-title-group">
          <Train className="icon-accent" size={22} />
          <div>
            <h2>{boardData?.station_name || 'Lucknow Charbagh (LKO)'}</h2>
            <span className="board-subtitle">
              Live Edge Cache (`lucknow_board.json` • 5-Min Auto-Poll)
            </span>
          </div>
        </div>
        <div className="board-badge">
          <Clock size={14} />
          <span>Sync: {String(boardData?.last_updated || '').slice(11, 19) || 'Live'}</span>
        </div>
      </div>

      <div className="board-table-wrapper">
        <table className="board-table">
          <thead>
            <tr>
              <th>Train No.</th>
              <th>Train Name / Route</th>
              <th>Arr / Dep</th>
              <th>Platform</th>
              <th>Live Status</th>
            </tr>
          </thead>
          <tbody>
            {trains.map((train) => {
              const isDelayed = Number(train.delay_minutes || 0) > 0;
              const isSelected = selectedTrainNo === train.train_number;
              return (
                <tr
                  key={train.train_number}
                  className={`board-row ${isSelected ? 'board-row-selected' : ''}`}
                  onClick={() =>
                    onSelectTrain(
                      `${train.train_number} ${train.train_name} kab aayegi aur platform number kya hai?`
                    )
                  }
                  title="Tap to ask RailAssist 3D about this train"
                >
                  <td className="train-no-cell">{train.train_number}</td>
                  <td>
                    <div className="train-name-primary">{train.train_name}</div>
                    <div className="train-route-sub">
                      <MapPin size={12} /> {train.origin} → {train.destination}
                    </div>
                  </td>
                  <td className="mono-cell">
                    {train.expected_arrival !== 'Source'
                      ? `Arr ${train.expected_arrival}`
                      : `Dep ${train.expected_departure}`}
                  </td>
                  <td>
                    <span className="platform-pill">PF {train.platform}</span>
                  </td>
                  <td>
                    <span
                      className={`status-pill ${
                        isDelayed ? 'status-delayed' : 'status-ontime'
                      }`}
                    >
                      {isDelayed ? (
                        <AlertTriangle size={14} />
                      ) : (
                        <CheckCircle2 size={14} />
                      )}
                      {train.status_en}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
