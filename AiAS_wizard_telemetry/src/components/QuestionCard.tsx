import { QuestionDefinition, AnswerValue } from '../types';
import { MultiSelectGrid, RankOrderCards, SliderControl } from './inputs';

interface QuestionCardProps {
  question: QuestionDefinition;
  value: AnswerValue;
  onChange: (value: AnswerValue) => void;
}

export const QuestionCard = ({ question, value, onChange }: QuestionCardProps) => {
  const choices = question.choices ?? [];

  return (
    <div className="question-card">
      <h2>{question.label}</h2>
      {question.helperText && <p>{question.helperText}</p>}

      {question.type === 'single_select' || question.type === 'tradeoff' || question.type === 'pledge' ? (
        <div className="choice-grid">
          {choices.map((c) => (
            <button
              type="button"
              key={c.id}
              onClick={() => onChange(String(c.value))}
              className={value === c.value ? 'selected' : ''}
            >
              {c.label}
            </button>
          ))}
        </div>
      ) : null}

      {question.type === 'multi_select' ? (
        <MultiSelectGrid choices={choices} value={(value as string[]) ?? []} onChange={onChange as (value: string[]) => void} />
      ) : null}

      {question.type === 'slider' ? (
        <SliderControl
          value={typeof value === 'number' ? value : Math.round(((question.max ?? 10) + (question.min ?? 1)) / 2)}
          min={question.min ?? 1}
          max={question.max ?? 10}
          step={question.step ?? 1}
          onChange={onChange as (value: number) => void}
        />
      ) : null}

      {question.type === 'rank_order' ? (
        <RankOrderCards choices={choices} value={(value as string[]) ?? []} onChange={onChange as (value: string[]) => void} />
      ) : null}

      {question.type === 'short_text' || question.type === 'long_text' ? (
        <textarea
          placeholder={question.placeholder}
          rows={question.type === 'short_text' ? 2 : 5}
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : null}
    </div>
  );
};
