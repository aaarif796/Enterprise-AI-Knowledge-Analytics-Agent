import type { ModelInfo } from '../types';

interface Props {
  models: ModelInfo[];
  selected: string;
  onSelect: (model: string) => void;
}

export default function ModelPicker({ models, selected, onSelect }: Props) {
  return (
    <div className="model-picker">
      <label htmlFor="model">Model</label>
      <select
        id="model"
        value={selected}
        onChange={(e) => onSelect(e.target.value)}
        title="Choose a model to save money - local/free options included"
      >
        <option value="">Auto (task-based routing)</option>
        {models.map((m, i) => (
          <option key={i} value={m.model}>
            {m.model} {m.free ? '🆓' : ''}
          </option>
        ))}
      </select>
    </div>
  );
}
