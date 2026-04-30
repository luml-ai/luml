import { Bell, ChartColumnBig, Link, Rocket } from 'lucide-vue-next'
import lumlflowQuickstart from '@/docs/lumlflow_quickstart.md?raw'
import lumlflowLlmEvaluation from '@/docs/llm_evaluation_lumlflow.md?raw'
import lumlflowTeamCollaboration from '@/docs/registry_module_draft.md?raw'
import lumlflowReleaseNotes from '@/docs/lumlflow_release_notes.md?raw'

export const TOP_CARDS = [
  {
    title: 'LUMLFlow Quickstart ',
    description:
      'Train a model, log metrics, and inspect your first experiment in LUMLFlow in under five minutes.',
    icon: Rocket,
    mdRaw: lumlflowQuickstart,
  },
  {
    title: 'LLM Evaluation with LUMLFlow',
    description:
      'Build a LangGraph agent with an LLM-as-judge node and run a full evaluation with custom scorers and trace capture.',
    icon: ChartColumnBig,
    mdRaw: lumlflowLlmEvaluation,
  },
  {
    title: 'Team Collaboration with LUML',
    description:
      'See how uploading from lumlflow to the Luml Registry turns solo experiments into shared, versioned, deployable assets.',
    icon: Link,
    mdRaw: lumlflowTeamCollaboration,
  },
  {
    title: 'LUMLFlow Release Notes',
    description: 'Catch up on the latest LUMLFlow features, fixes, and breaking changes.',
    icon: Bell,
    mdRaw: lumlflowReleaseNotes,
  },
]
