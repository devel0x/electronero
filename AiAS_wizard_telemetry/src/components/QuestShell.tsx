import { useEffect, useMemo, useState } from 'react';
import { wizardDefinition } from '../data/wizardData';
import { deriveProfile } from '../logic/deriveProfile';
import { grantChapterReward, initialRewardState } from '../logic/rewards';
import { getTelemetryEvents } from '../telemetry/telemetry';
import { useTelemetry } from '../telemetry/TelemetryContext';
import { AnswerValue, UserAnswer } from '../types';
import { AnalyticsDashboard } from './AnalyticsDashboard';
import { ChapterSidebar } from './ChapterSidebar';
import { CompletionScreen } from './CompletionScreen';
import { ProgressMeter } from './ProgressMeter';
import { QuestionCard } from './QuestionCard';
import { ReasoningPanel } from './ReasoningPanel';
import { RewardToast } from './RewardToast';

const STORAGE_KEY = 'aias_quest_state_v1';

export const QuestShell = () => {
  const { emit } = useTelemetry();
  const userId = 'demo_user_001';
  const sessionId = useMemo(() => crypto.randomUUID(), []);

  const chaptersWithQuestions = wizardDefinition.chapters.filter((c) => c.questions.length > 0);
  const flatQuestions = chaptersWithQuestions.flatMap((c) => c.questions);

  const [questionIndex, setQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, UserAnswer>>({});
  const [completedChapterIds, setCompletedChapterIds] = useState<Record<string, boolean>>({});
  const [rewardState, setRewardState] = useState(initialRewardState);
  const [toast, setToast] = useState<string | null>(null);
  const [startedAt] = useState<number>(Date.now());
  const [questionStartedAt, setQuestionStartedAt] = useState<number>(Date.now());

  const currentQuestion = flatQuestions[questionIndex];
  const isComplete = questionIndex >= flatQuestions.length;

  useEffect(() => {
    emit({
      eventName: 'wizard_started',
      userId,
      sessionId,
      wizardId: wizardDefinition.id,
      stepIndex: 0,
      metadata: { title: wizardDefinition.title }
    });

    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved) as {
        questionIndex: number;
        answers: Record<string, UserAnswer>;
        completedChapterIds: Record<string, boolean>;
      };
      setQuestionIndex(parsed.questionIndex);
      setAnswers(parsed.answers);
      setCompletedChapterIds(parsed.completedChapterIds);
      emit({
        eventName: 'wizard_resumed',
        userId,
        sessionId,
        wizardId: wizardDefinition.id,
        stepIndex: parsed.questionIndex,
        metadata: { source: 'local_storage' },
        extra: { resumed_after_ms: Date.now() - startedAt }
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        questionIndex,
        answers,
        completedChapterIds
      })
    );
  }, [answers, completedChapterIds, questionIndex]);

  useEffect(() => {
    if (!currentQuestion) return;
    emit({
      eventName: 'question_viewed',
      userId,
      sessionId,
      wizardId: wizardDefinition.id,
      chapterId: currentQuestion.chapterId,
      questionId: currentQuestion.id,
      stepIndex: questionIndex,
      answerType: currentQuestion.type,
      metadata: { chapter: currentQuestion.chapterId }
    });
    setQuestionStartedAt(Date.now());
  }, [currentQuestion, emit, questionIndex, sessionId, userId]);

  const progress = Math.round((Math.min(questionIndex, flatQuestions.length) / flatQuestions.length) * 100);

  const onAnswerChange = (value: AnswerValue) => {
    if (!currentQuestion) return;
    const exists = answers[currentQuestion.id];
    const newAnswer: UserAnswer = {
      questionId: currentQuestion.id,
      chapterId: currentQuestion.chapterId,
      value,
      answeredAt: new Date().toISOString(),
      timeOnQuestionMs: Date.now() - questionStartedAt
    };

    setAnswers((prev) => ({ ...prev, [currentQuestion.id]: newAnswer }));
    emit({
      eventName: exists ? 'answer_changed' : 'question_answered',
      userId,
      sessionId,
      wizardId: wizardDefinition.id,
      chapterId: currentQuestion.chapterId,
      questionId: currentQuestion.id,
      stepIndex: questionIndex,
      answerType: currentQuestion.type,
      metadata: { value },
      extra: { time_on_question_ms: Date.now() - questionStartedAt }
    });

    if (currentQuestion.id === 'autonomy_level') {
      emit({
        eventName: 'autonomy_level_selected',
        userId,
        sessionId,
        wizardId: wizardDefinition.id,
        chapterId: currentQuestion.chapterId,
        questionId: currentQuestion.id,
        stepIndex: questionIndex,
        answerType: currentQuestion.type,
        metadata: { autonomy: value }
      });
    }
    if (currentQuestion.id === 'guardrail_level') {
      emit({
        eventName: 'guardrail_level_selected',
        userId,
        sessionId,
        wizardId: wizardDefinition.id,
        chapterId: currentQuestion.chapterId,
        questionId: currentQuestion.id,
        stepIndex: questionIndex,
        answerType: currentQuestion.type,
        metadata: { guardrail: value }
      });
    }
  };

  const advance = () => {
    if (!currentQuestion) return;
    const chapter = chaptersWithQuestions.find((c) => c.id === currentQuestion.chapterId);
    if (!chapter) return;

    const chapterDone = chapter.questions.every((q) => Boolean(answers[q.id]));
    if (chapterDone && !completedChapterIds[chapter.id]) {
      setCompletedChapterIds((prev) => ({ ...prev, [chapter.id]: true }));
      setRewardState((prev) => grantChapterReward(prev, chapter.id, chapter.xpReward));
      emit({
        eventName: 'chapter_completed',
        userId,
        sessionId,
        wizardId: wizardDefinition.id,
        chapterId: chapter.id,
        stepIndex: questionIndex,
        metadata: { xpReward: chapter.xpReward },
        extra: { chapter_completion_time_ms: Date.now() - startedAt }
      });
      setToast(`${chapter.title} complete! +${chapter.xpReward} XP`);
      setTimeout(() => setToast(null), 1800);
    }

    setQuestionIndex((i) => i + 1);
  };

  const skip = () => {
    if (!currentQuestion) return;
    emit({
      eventName: 'question_skipped',
      userId,
      sessionId,
      wizardId: wizardDefinition.id,
      chapterId: currentQuestion.chapterId,
      questionId: currentQuestion.id,
      stepIndex: questionIndex,
      answerType: currentQuestion.type,
      metadata: {},
      extra: {
        questions_skipped_count: flatQuestions.filter((q) => !answers[q.id]).length
      }
    });
    setQuestionIndex((i) => i + 1);
  };

  const profile = deriveProfile(Object.values(answers));

  useEffect(() => {
    if (isComplete) {
      emit({
        eventName: 'profile_generated',
        userId,
        sessionId,
        wizardId: wizardDefinition.id,
        chapterId: 'profile_reveal',
        stepIndex: questionIndex,
        metadata: { archetype: profile.archetype }
      });
      emit({
        eventName: 'archetype_assigned',
        userId,
        sessionId,
        wizardId: wizardDefinition.id,
        chapterId: 'profile_reveal',
        stepIndex: questionIndex,
        metadata: { archetype: profile.archetype }
      });
      emit({
        eventName: 'wizard_completed',
        userId,
        sessionId,
        wizardId: wizardDefinition.id,
        chapterId: 'profile_reveal',
        stepIndex: questionIndex,
        metadata: {},
        extra: {
          total_session_time_ms: Date.now() - startedAt,
          questions_answered_count: Object.keys(answers).length,
          questions_skipped_count: flatQuestions.length - Object.keys(answers).length
        }
      });
    }
  }, [answers, emit, isComplete, profile.archetype, questionIndex, sessionId, startedAt, userId, flatQuestions.length]);

  if (isComplete) {
    return (
      <div className="quest-shell">
        <CompletionScreen
          profile={profile}
          rewards={grantChapterReward(rewardState, 'profile_reveal', 200)}
          onAction={(action) =>
            emit({
              eventName: 'recommended_action_clicked',
              userId,
              sessionId,
              wizardId: wizardDefinition.id,
              chapterId: 'profile_reveal',
              stepIndex: questionIndex,
              metadata: { action }
            })
          }
        />
        <AnalyticsDashboard events={getTelemetryEvents()} />
      </div>
    );
  }

  const activeChapter = wizardDefinition.chapters.find((c) => c.id === currentQuestion.chapterId) ?? wizardDefinition.chapters[0];

  return (
    <div className="quest-shell">
      <ChapterSidebar
        chapters={wizardDefinition.chapters}
        activeChapterId={activeChapter.id}
        completion={completedChapterIds}
        rewardState={rewardState}
      />

      <main>
        <header>
          <h1>{wizardDefinition.title}</h1>
          <p>{activeChapter.subtitle}</p>
          <ProgressMeter value={progress} />
        </header>

        <QuestionCard question={currentQuestion} value={answers[currentQuestion.id]?.value ?? null} onChange={onAnswerChange} />

        <div className="action-bar">
          <button type="button" onClick={() => setQuestionIndex((i) => Math.max(0, i - 1))}>Previous</button>
          <button type="button" onClick={advance}>Next</button>
          <button type="button" onClick={skip}>Skip</button>
          <button
            type="button"
            onClick={() => {
              emit({
                eventName: 'reward_claimed',
                userId,
                sessionId,
                wizardId: wizardDefinition.id,
                chapterId: activeChapter.id,
                questionId: currentQuestion.id,
                stepIndex: questionIndex,
                metadata: { action: 'save_continue_later' }
              });
            }}
          >
            Save & continue later
          </button>
          <button
            type="button"
            onClick={() =>
              emit({
                eventName: 'reward_preview_opened',
                userId,
                sessionId,
                wizardId: wizardDefinition.id,
                chapterId: activeChapter.id,
                questionId: currentQuestion.id,
                stepIndex: questionIndex,
                metadata: { xp: activeChapter.xpReward }
              })
            }
          >
            Claim reward
          </button>
        </div>
      </main>

      <ReasoningPanel summary={currentQuestion.reasoningSummary} unlockHint="Next chapter unlocks deeper personalization and workflow quests." />
      {toast && <RewardToast message={toast} />}
    </div>
  );
};
