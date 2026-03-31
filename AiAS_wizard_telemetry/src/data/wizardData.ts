import { WizardDefinition } from '../types';

export const wizardDefinition: WizardDefinition = {
  id: 'ai_alignment_builder_quest_v1',
  title: 'AI Alignment & Builder Quest',
  chapters: [
    {
      id: 'who_you_are',
      title: 'Who You Are',
      subtitle: 'Calibrating your builder identity',
      xpReward: 80,
      questions: [
        {
          id: 'role_persona',
          chapterId: 'who_you_are',
          label: 'Which role best describes you?',
          helperText: 'Choose the role closest to how you spend most of your time.',
          type: 'single_select',
          choices: [
            { id: 'builder', label: 'Builder', value: 'Builder' },
            { id: 'operator', label: 'Operator', value: 'Operator' },
            { id: 'creator', label: 'Creator', value: 'Creator' },
            { id: 'team_lead', label: 'Team Lead', value: 'Team Lead' }
          ],
          analytics: { category: 'persona', funnelStage: 'early' },
          reasoningSummary: 'Role helps tailor recommendations and workflow defaults.'
        },
        {
          id: 'industry_context',
          chapterId: 'who_you_are',
          label: 'What kind of work do you do most often?',
          type: 'single_select',
          choices: [
            { id: 'engineering', label: 'Engineering / Product', value: 'Engineering' },
            { id: 'marketing', label: 'Marketing / Growth', value: 'Marketing' },
            { id: 'operations', label: 'Operations / Strategy', value: 'Operations' },
            { id: 'education', label: 'Education / Research', value: 'Education' }
          ],
          analytics: { category: 'context', funnelStage: 'early' },
          reasoningSummary: 'Context shapes language, examples, and guardrail strictness.'
        },
        {
          id: 'technical_comfort',
          chapterId: 'who_you_are',
          label: 'How technically comfortable are you?',
          type: 'slider',
          min: 1,
          max: 10,
          step: 1,
          analytics: { category: 'readiness', funnelStage: 'early' }
        }
      ]
    },
    {
      id: 'use_today',
      title: 'How You Use AI Today',
      subtitle: 'Current stack and pain points',
      xpReward: 120,
      questions: [
        {
          id: 'ai_usage_frequency',
          chapterId: 'use_today',
          label: 'How often do you use AI today?',
          type: 'single_select',
          choices: [
            { id: 'daily', label: 'Daily', value: 'daily' },
            { id: 'weekly', label: 'Weekly', value: 'weekly' },
            { id: 'monthly', label: 'Monthly', value: 'monthly' },
            { id: 'rarely', label: 'Rarely', value: 'rarely' }
          ],
          analytics: { category: 'usage', funnelStage: 'mid' },
          reasoningSummary: 'Frequency is the strongest signal for maturity and onboarding depth.'
        },
        {
          id: 'tools_used',
          chapterId: 'use_today',
          label: 'Which AI tools do you use most?',
          type: 'multi_select',
          choices: [
            { id: 'chat_assistant', label: 'Chat assistants', value: 'chat_assistant' },
            { id: 'code_assistant', label: 'Code assistants', value: 'code_assistant' },
            { id: 'image_tools', label: 'Image/video tools', value: 'image_tools' },
            { id: 'automation', label: 'Automation agents', value: 'automation' }
          ],
          analytics: { category: 'tooling', funnelStage: 'mid' }
        },
        {
          id: 'pain_points',
          chapterId: 'use_today',
          label: 'What frustrates you most about current AI tools?',
          type: 'long_text',
          placeholder: 'Example: Inconsistent quality and limited workflow memory.',
          analytics: { category: 'pain_points', funnelStage: 'mid' }
        }
      ]
    },
    {
      id: 'use_future',
      title: 'How You Want to Use AI in the Future',
      subtitle: 'Future intent and desired automation',
      xpReward: 130,
      questions: [
        {
          id: 'future_use_cases',
          chapterId: 'use_future',
          label: 'How do you see yourself using AI in the future?',
          type: 'multi_select',
          choices: [
            { id: 'research', label: 'Research and synthesis', value: 'research' },
            { id: 'automation', label: 'Workflow automation', value: 'automation' },
            { id: 'creative', label: 'Creative generation', value: 'creative' },
            { id: 'decision_support', label: 'Decision support', value: 'decision_support' }
          ],
          analytics: { category: 'future_intent', funnelStage: 'mid' }
        },
        {
          id: 'ai_handle_for_you',
          chapterId: 'use_future',
          label: 'What would you most like AI to handle for you?',
          type: 'short_text',
          placeholder: 'Describe your highest-value delegation target.',
          analytics: { category: 'delegation', funnelStage: 'mid' }
        }
      ]
    },
    {
      id: 'workflow_preferences',
      title: 'Workflow & Interaction Preferences',
      subtitle: 'How AI should collaborate with you',
      xpReward: 120,
      questions: [
        {
          id: 'interaction_modes',
          chapterId: 'workflow_preferences',
          label: 'Do you prefer chat, wizard flows, templates, dashboards, or agents?',
          type: 'rank_order',
          choices: [
            { id: 'chat', label: 'Chat', value: 'chat' },
            { id: 'wizard', label: 'Wizard flows', value: 'wizard' },
            { id: 'templates', label: 'Templates', value: 'templates' },
            { id: 'dashboards', label: 'Dashboards', value: 'dashboards' },
            { id: 'agents', label: 'Agents', value: 'agents' }
          ],
          analytics: { category: 'interaction', funnelStage: 'mid' }
        },
        {
          id: 'reasoning_confidence',
          chapterId: 'workflow_preferences',
          label: 'Do you want reasoning summaries and confidence indicators?',
          type: 'tradeoff',
          choices: [
            { id: 'concise', label: 'Fast + concise', value: 'concise' },
            { id: 'balanced', label: 'Balanced detail', value: 'balanced' },
            { id: 'deep', label: 'Deep reasoning visibility', value: 'deep' }
          ],
          analytics: { category: 'explainability', funnelStage: 'mid' },
          reasoningSummary: 'This calibrates transparency controls and output style.'
        }
      ]
    },
    {
      id: 'trust_autonomy_safety',
      title: 'Trust, Autonomy, and Safety',
      subtitle: 'Set your control envelope',
      xpReward: 150,
      questions: [
        {
          id: 'autonomy_level',
          chapterId: 'trust_autonomy_safety',
          label: 'How much autonomy should AI have?',
          type: 'slider',
          min: 1,
          max: 10,
          step: 1,
          analytics: { category: 'autonomy', funnelStage: 'late' }
        },
        {
          id: 'requires_approval',
          chapterId: 'trust_autonomy_safety',
          label: 'Which actions should always require approval?',
          type: 'multi_select',
          choices: [
            { id: 'external_send', label: 'Sending external messages', value: 'external_send' },
            { id: 'financial', label: 'Financial transactions', value: 'financial' },
            { id: 'security', label: 'Security / access changes', value: 'security' },
            { id: 'publish', label: 'Publishing content', value: 'publish' }
          ],
          analytics: { category: 'safety', funnelStage: 'late' }
        },
        {
          id: 'guardrail_level',
          chapterId: 'trust_autonomy_safety',
          label: 'What guardrail style fits you best?',
          type: 'single_select',
          choices: [
            { id: 'strict', label: 'High safety guardrails', value: 'strict' },
            { id: 'balanced', label: 'Balanced flexibility', value: 'balanced' },
            { id: 'experimental', label: 'Experimental mode', value: 'experimental' }
          ],
          analytics: { category: 'guardrails', funnelStage: 'late' }
        }
      ]
    },
    {
      id: 'success_metrics',
      title: 'Success Metrics & Goals',
      subtitle: 'Define mission success',
      xpReward: 110,
      questions: [
        {
          id: 'outcome_priority',
          chapterId: 'success_metrics',
          label: 'What outcome matters most?',
          type: 'single_select',
          choices: [
            { id: 'time_savings', label: 'Time savings', value: 'time_savings' },
            { id: 'quality', label: 'Output quality', value: 'quality' },
            { id: 'learning', label: 'Learning velocity', value: 'learning' },
            { id: 'revenue', label: 'Revenue impact', value: 'revenue' }
          ],
          analytics: { category: 'goals', funnelStage: 'late' }
        },
        {
          id: 'essential_trigger',
          chapterId: 'success_metrics',
          label: 'What would make AI feel essential to your workflow?',
          type: 'long_text',
          analytics: { category: 'activation', funnelStage: 'late' }
        }
      ]
    },
    {
      id: 'responsibility_pledge',
      title: 'AI Responsibility Pledge',
      subtitle: 'Align with safe and ethical use',
      xpReward: 140,
      questions: [
        {
          id: 'responsibility_pledge',
          chapterId: 'responsibility_pledge',
          label:
            'I will use AI to assist, create, learn, and build responsibly. I understand AI outputs may require verification, human judgment, and oversight.',
          helperText: 'Choose your preferred safety mode.',
          type: 'pledge',
          choices: [
            { id: 'agree', label: 'I agree', value: 'agree' },
            { id: 'agree_strong', label: 'I agree and want strong guardrails', value: 'agree_strong' },
            { id: 'agree_balanced', label: 'I agree and want balanced flexibility', value: 'agree_balanced' },
            { id: 'review_first', label: 'Review safety principles first', value: 'review_first' }
          ],
          analytics: { category: 'trust', funnelStage: 'final' },
          reasoningSummary: 'Pledge preference configures policy defaults and compliance UX.'
        }
      ]
    },
    {
      id: 'profile_reveal',
      title: 'Final Builder Profile Reveal',
      subtitle: 'Generate your personalized AI profile',
      xpReward: 200,
      questions: []
    }
  ]
};
