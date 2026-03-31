import { DerivedProfile, RewardState } from '../types';
import { ArchetypeReveal } from './ArchetypeReveal';
import { ProfileCard } from './ProfileCard';

export const CompletionScreen = ({ profile, rewards, onAction }: { profile: DerivedProfile; rewards: RewardState; onAction: (action: string) => void }) => (
  <section className="completion-screen">
    <ArchetypeReveal archetype={profile.archetype} />
    <ProfileCard profile={profile} rewards={rewards} />
    <h3>Recommended next actions</h3>
    <div className="choice-grid">
      {['Start First Quest', 'Explore Recommended Tools', 'Customize My Guardrails', 'View My AI Profile'].map((action) => (
        <button key={action} type="button" onClick={() => onAction(action)}>
          {action}
        </button>
      ))}
    </div>
  </section>
);
