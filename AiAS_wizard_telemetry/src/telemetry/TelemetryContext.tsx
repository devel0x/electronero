import React, { createContext, useContext } from 'react';
import { track } from './telemetry';
import { QuestionType } from '../types';

interface TelemetryContextValue {
  emit: (params: {
    eventName: string;
    userId: string;
    sessionId: string;
    wizardId: string;
    chapterId?: string;
    questionId?: string;
    stepIndex: number;
    answerType?: QuestionType;
    metadata?: Record<string, unknown>;
    extra?: Record<string, unknown>;
  }) => void;
}

const TelemetryContext = createContext<TelemetryContextValue | null>(null);

export const TelemetryProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const emit: TelemetryContextValue['emit'] = ({
    eventName,
    userId,
    sessionId,
    wizardId,
    chapterId,
    questionId,
    stepIndex,
    answerType,
    metadata = {},
    extra = {}
  }) => {
    track(eventName, {
      user_id: userId,
      session_id: sessionId,
      wizard_id: wizardId,
      chapter_id: chapterId,
      question_id: questionId,
      timestamp: new Date().toISOString(),
      step_index: stepIndex,
      answer_type: answerType,
      metadata,
      ...extra
    });
  };

  return <TelemetryContext.Provider value={{ emit }}>{children}</TelemetryContext.Provider>;
};

export const useTelemetry = (): TelemetryContextValue => {
  const ctx = useContext(TelemetryContext);
  if (!ctx) {
    throw new Error('useTelemetry must be used within TelemetryProvider');
  }
  return ctx;
};
