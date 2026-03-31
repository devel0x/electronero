import { ChoiceOption } from '../types';

export const MultiSelectGrid = ({
  choices,
  value,
  onChange
}: {
  choices: ChoiceOption[];
  value: string[];
  onChange: (next: string[]) => void;
}) => (
  <div className="choice-grid">
    {choices.map((choice) => {
      const selected = value.includes(String(choice.value));
      return (
        <button
          key={choice.id}
          className={selected ? 'selected' : ''}
          onClick={() =>
            onChange(selected ? value.filter((v) => v !== choice.value) : [...value, String(choice.value)])
          }
          type="button"
        >
          {choice.label}
        </button>
      );
    })}
  </div>
);

export const SliderControl = ({ value, min, max, step, onChange }: { value: number; min: number; max: number; step: number; onChange: (n: number) => void }) => (
  <div>
    <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    <p>{value}</p>
  </div>
);

export const RankOrderCards = ({
  choices,
  value,
  onChange
}: {
  choices: ChoiceOption[];
  value: string[];
  onChange: (next: string[]) => void;
}) => (
  <div className="rank-list">
    {choices.map((c) => (
      <button
        type="button"
        key={c.id}
        onClick={() => onChange(value.includes(String(c.value)) ? value : [...value, String(c.value)])}
      >
        {value.indexOf(String(c.value)) >= 0 ? `${value.indexOf(String(c.value)) + 1}. ` : ''}
        {c.label}
      </button>
    ))}
  </div>
);
