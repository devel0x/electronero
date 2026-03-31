import { DerivedProfile, RewardState } from '../types';

export const ProfileCard = ({ profile, rewards }: { profile: DerivedProfile; rewards: RewardState }) => (
  <div className="profile-card">
    <h2>{profile.archetype} Archetype</h2>
    <p>Maturity: {profile.aiMaturityScore}/100</p>
    <p>Autonomy comfort: {profile.autonomyComfortScore}/100</p>
    <p>Guardrail style: {profile.trustGuardrailPreference}</p>
    <p>Use-case cluster: {profile.topUseCaseCluster}</p>
    <p>{profile.summaryNow}</p>
    <p>{profile.summaryFuture}</p>
    <p>Rewards: {rewards.xp} XP • {rewards.badges.join(', ')}</p>
  </div>
);
