interface ProgressMeterProps {
  value: number;
}

export const ProgressMeter = ({ value }: ProgressMeterProps) => (
  <div className="progress-meter" aria-label={`Progress ${value}%`}>
    <div className="progress-meter__fill" style={{ width: `${value}%` }} />
    <span>{value}% complete</span>
  </div>
);
