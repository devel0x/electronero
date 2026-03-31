import { ChapterDefinition, RewardState } from '../types';

interface ChapterSidebarProps {
  chapters: ChapterDefinition[];
  activeChapterId: string;
  completion: Record<string, boolean>;
  rewardState: RewardState;
}

export const ChapterSidebar = ({ chapters, activeChapterId, completion, rewardState }: ChapterSidebarProps) => (
  <aside className="sidebar left">
    <h2>Mission Chapters</h2>
    <ul>
      {chapters.map((chapter, index) => (
        <li key={chapter.id} className={activeChapterId === chapter.id ? 'active' : completion[chapter.id] ? 'done' : ''}>
          <span>{index + 1}. {chapter.title}</span>
        </li>
      ))}
    </ul>
    <div className="reward-box">
      <p>XP: {rewardState.xp}</p>
      <p>Streak: {rewardState.streak}</p>
      <p>Badges: {rewardState.badges.join(', ') || 'None yet'}</p>
    </div>
  </aside>
);
