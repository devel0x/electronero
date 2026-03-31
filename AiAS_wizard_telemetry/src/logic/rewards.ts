import { RewardState } from '../types';

export const initialRewardState: RewardState = {
  xp: 0,
  streak: 0,
  badges: [],
  rewardsClaimed: []
};

export const grantChapterReward = (state: RewardState, chapterId: string, xp: number): RewardState => {
  const badges = [...state.badges];
  if (xp >= 140 && !badges.includes('Trust Sentinel')) badges.push('Trust Sentinel');
  if (chapterId === 'profile_reveal' && !badges.includes('Profile Unlocked')) badges.push('Profile Unlocked');

  return {
    xp: state.xp + xp,
    streak: state.streak + 1,
    badges,
    rewardsClaimed: [...state.rewardsClaimed, chapterId]
  };
};
