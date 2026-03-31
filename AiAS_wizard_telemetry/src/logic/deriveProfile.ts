import { DerivedProfile, UserAnswer } from '../types';

const answerMap = (answers: UserAnswer[]) =>
  answers.reduce<Record<string, UserAnswer['value']>>((acc, answer) => {
    acc[answer.questionId] = answer.value;
    return acc;
  }, {});

export const deriveProfile = (answers: UserAnswer[]): DerivedProfile => {
  const map = answerMap(answers);
  const technical = Number(map.technical_comfort ?? 5);
  const autonomy = Number(map.autonomy_level ?? 5);
  const usage = String(map.ai_usage_frequency ?? 'monthly');
  const role = String(map.role_persona ?? 'Explorer');
  const guardrails = String(map.guardrail_level ?? 'balanced');
  const futureUseCases = (map.future_use_cases as string[] | undefined) ?? [];

  const usageScore = usage === 'daily' ? 35 : usage === 'weekly' ? 25 : usage === 'monthly' ? 15 : 8;
  const aiMaturityScore = Math.min(100, Math.round(usageScore + technical * 5 + futureUseCases.length * 8));

  const topUseCaseCluster = futureUseCases[0] ?? 'general_productivity';
  const archetype = role === 'Builder' && autonomy >= 7 ? 'Power User' : role;

  return {
    archetype,
    aiMaturityScore,
    autonomyComfortScore: autonomy * 10,
    trustGuardrailPreference: guardrails,
    topUseCaseCluster,
    summaryNow: `You currently operate in a ${usage} AI rhythm with technical comfort at ${technical}/10.`,
    summaryFuture: `You want AI to prioritize ${futureUseCases.join(', ') || 'high-impact workflow acceleration'} with ${guardrails} guardrails.`,
    recommendation: {
      nextQuest: autonomy > 6 ? 'Agent Automation Sprint' : 'Confidence Copilot Foundations',
      featureRecommendations: [
        'Adaptive workspace presets',
        'Reasoning summaries + confidence indicators',
        'Guardrail policy control center'
      ],
      successBlueprint: [
        'Launch one high-value workflow',
        'Track weekly time savings',
        'Review safety checkpoints bi-weekly'
      ]
    }
  };
};
