interface Props {
  value: number; // 0..1
  label?: string;
}

export default function ConfidenceBar({ value, label = 'Confidence' }: Props) {
  const pct = Math.round(value * 100);
  const color = value >= 0.7 ? '#22c55e' : value >= 0.4 ? '#eab308' : '#ef4444';
  return (
    <div className="confidence">
      <div className="confidence-head">
        <span>{label}</span>
        <span style={{ color }}>{pct}%</span>
      </div>
      <div className="confidence-track">
        <div
          className="confidence-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}
