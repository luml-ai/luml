import { CircleArrowDown, CircleArrowUp, FileText, ChartBar, Smile, Target } from 'lucide-vue-next'

export const COLUMNS_ICONS = {
  inputs: CircleArrowDown,
  outputs: CircleArrowUp,
  refs: FileText,
  scores: ChartBar,
  feedback: Smile,
  expectation: Target,
}

export const COLUMNS_TITLES_MAP = {
  id: 'ID',
  modelId: 'Artifact name',
  feedback: 'feedback',
  inputs: 'inputs',
  outputs: 'outputs',
  refs: 'references',
  scores: 'scores',
  expectation: 'expectation',
}
