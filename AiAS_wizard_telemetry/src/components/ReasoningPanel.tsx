interface ReasoningPanelProps {
  summary?: string;
  unlockHint: string;
}

export const ReasoningPanel = ({ summary, unlockHint }: ReasoningPanelProps) => (
  <aside className="sidebar right">
    <h3>Why this matters</h3>
    <p>{summary ?? 'Your answers help shape adaptive AI behavior and onboarding depth.'}</p>
    <h4>What unlocks next</h4>
    <p>{unlockHint}</p>
  </aside>
);
