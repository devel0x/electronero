export type QuestionType =
  | 'single_select'
  | 'multi_select'
  | 'slider'
  | 'rank_order'
  | 'short_text'
  | 'long_text'
  | 'tradeoff'
  | 'pledge';

export interface ChoiceOption {
  id: string;
  label: string;
  description?: string;
  value: string | number;
  icon?: string;
  analyticsTag?: string;
}

export interface QuestionDefinition {
  id: string;
  label: string;
  helperText?: string;
  type: QuestionType;
  choices?: ChoiceOption[];
  chapterId: string;
  required?: boolean;
  placeholder?: string;
  analytics: {
    category: string;
    funnelStage: string;
    intentSignal?: string;
  };
  reasoningSummary?: string;
  min?: number;
  max?: number;
  step?: number;
}

export interface ChapterDefinition {
  id: string;
  title: string;
  subtitle: string;
  xpReward: number;
  questions: QuestionDefinition[];
}

export interface WizardDefinition {
  id: string;
  title: string;
  chapters: ChapterDefinition[];
}

export type AnswerValue = string | number | string[] | null;

export interface UserAnswer {
  questionId: string;
  chapterId: string;
  value: AnswerValue;
  answeredAt: string;
  timeOnQuestionMs?: number;
}

export interface TelemetryEvent {
  eventName: string;
  user_id: string;
  session_id: string;
  wizard_id: string;
  chapter_id?: string;
  question_id?: string;
  timestamp: string;
  step_index: number;
  answer_type?: QuestionType;
  metadata: Record<string, unknown>;
  time_on_question_ms?: number;
  total_session_time_ms?: number;
  questions_skipped_count?: number;
  questions_answered_count?: number;
  chapter_completion_time_ms?: number;
  dropoff_question_id?: string;
  resumed_after_ms?: number;
}

export interface RewardState {
  xp: number;
  streak: number;
  badges: string[];
  rewardsClaimed: string[];
}

export interface RecommendationResult {
  nextQuest: string;
  featureRecommendations: string[];
  successBlueprint: string[];
}

export interface DerivedProfile {
  archetype: string;
  aiMaturityScore: number;
  autonomyComfortScore: number;
  trustGuardrailPreference: string;
  topUseCaseCluster: string;
  recommendation: RecommendationResult;
  summaryNow: string;
  summaryFuture: string;
}
