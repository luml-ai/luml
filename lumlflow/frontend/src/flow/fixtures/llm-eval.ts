/**
 * Scenario (b): LLM evaluation.
 *
 * Same asset semantics as the churn flow, with two differences that matter for
 * the UI: the eval asset is non-deterministic (so two materializations of one
 * version can disagree, and the comparison surface has to warn), and traces live
 * *inside* the EvalBundle rather than being assets of their own.
 */

import type { AssetVersion, Branch, FlowSession, Materialization, Transaction } from '../types'
import { makeMaterialization, makeVersion, seeded } from './helpers'

const versions: AssetVersion[] = []
const materializations: Record<string, Materialization> = {}
const push = (version: AssetVersion): AssetVersion => {
  versions.push(version)
  return version
}

const dataset = push(
  makeVersion({
    assetId: 'e_dataset',
    name: 'SupportQA',
    kind: 'source',
    params: { split: 'validation', n: 240 },
    source: `class SupportQA(Asset):
    """240 support questions with reference answers."""
    split: str = "validation"
    n: int = 240

    def materialize(self) -> Frame:
        return load_dataset("support_qa")[self.split].select(range(self.n))`,
    doc: '240 support questions with reference answers.',
    outputs: [{ name: 'value', kind: 'frame', content: 'support-qa' }],
    step: 1,
    author: 'human',
    intent: 'Load the support QA validation split',
    tag: 'v1',
  }),
)

const promptSource = (style: string, body: string): string => `class Prompt(Asset):
    """${style}"""
    template: str = """${body}"""

    def materialize(self) -> Note:
        return Note(self.template)`

const promptV1 = push(
  makeVersion({
    assetId: 'e_prompt',
    name: 'Prompt',
    kind: 'note',
    source: promptSource('Terse system prompt.', 'Answer the support question. Be brief.'),
    doc: 'Terse system prompt.',
    outputs: [{ name: 'value', kind: 'note', content: 'prompt-terse' }],
    step: 2,
    author: 'human',
    intent: 'First pass at the system prompt',
    tag: 'v1',
  }),
)

const promptV2 = push(
  makeVersion({
    assetId: 'e_prompt',
    name: 'Prompt',
    kind: 'note',
    source: promptSource(
      'Adds citation requirement. The terse prompt hallucinated policy numbers.',
      'Answer the support question using only the provided policy text. Cite the clause you used. If the policy does not cover it, say so.',
    ),
    doc: 'Adds citation requirement. The terse prompt hallucinated policy numbers.',
    outputs: [{ name: 'value', kind: 'note', content: 'prompt-cited' }],
    step: 8,
    author: 'agent-1',
    intent: 'Require citations to stop policy hallucination',
    tag: 'v2',
  }),
)

const answersFor = (tag: string, model: string, step: number, author: string, intent: string) =>
  push(
    makeVersion({
      assetId: 'e_answers',
      name: 'Answers',
      kind: 'frame',
      deps: ['e_dataset', 'e_prompt'],
      params: { model, temperature: 0 },
      source: `class Answers(Asset):
    """Model answers for every question in the set."""
    data: SupportQA
    prompt: Prompt
    model: str = "${model}"
    temperature: float = 0.0

    def materialize(self) -> Frame:
        return self.data.map(lambda row: complete(self.model, self.prompt, row))`,
      doc: 'Model answers for every question in the set.',
      volatility: 'nondeterministic',
      outputs: [{ name: 'value', kind: 'frame', content: `answers-${tag}` }],
      step,
      author,
      intent,
      tag,
    }),
  )

const answersHaiku = answersFor('v1', 'claude-haiku-4-5', 3, 'human', 'Run the baseline model')
const answersSonnet = answersFor('v2', 'claude-sonnet-5', 12, 'agent-2', 'Try a stronger model')

const evalSource = `class QAEval(Asset):
    """Grade answers for correctness and groundedness."""
    answers: Answers
    data: SupportQA
    dataset: str = "support_qa/validation"

    def materialize(self) -> EvalBundle:
        return evaluate(self.answers, self.data, scorers=[correctness, groundedness])`

const evalVersion = (tag: string, step: number, author: string, intent: string) =>
  push(
    makeVersion({
      assetId: 'e_eval',
      name: 'QAEval',
      kind: 'eval',
      deps: ['e_answers', 'e_dataset'],
      params: { dataset: 'support_qa/validation' },
      source: evalSource,
      doc: 'Grade answers for correctness and groundedness.',
      volatility: 'nondeterministic',
      outputs: [
        { name: 'scores', kind: 'metric', content: `scores-${tag}` },
        { name: 'traces', kind: 'eval', content: `traces-${tag}` },
      ],
      step,
      author,
      intent,
      tag,
    }),
  )

const evalBaseline = evalVersion('v1', 4, 'human', 'Run the baseline model')
const evalCited = evalVersion('v2', 9, 'agent-1', 'Require citations to stop policy hallucination')
const evalSonnet = evalVersion('v3', 13, 'agent-2', 'Try a stronger model')

const rand = seeded(7)
const traces = (scoreBase: number) =>
  Array.from({ length: 6 }, (_, i) => ({
    sampleId: `q-${100 + i}`,
    prompt: [
      'Can I cancel within the first 14 days?',
      'Does the warranty cover water damage?',
      'How do I change the billing address on an active plan?',
      'Is roaming included in the base tier?',
      'What happens to my number if I port out mid-cycle?',
      'Can two lines share one data allowance?',
    ][i],
    output: [
      'Yes. Clause 4.2 allows cancellation within 14 days of activation for a full refund.',
      'No. Clause 9.1 excludes liquid ingress from the standard warranty.',
      'Billing address changes are handled in Account → Billing; the policy text does not cover this.',
      'Roaming is not included in the base tier (clause 12.4).',
      'Porting out mid-cycle ends the contract at the port date; clause 7.7 applies.',
      'The policy text does not cover shared allowances.',
    ][i],
    score: Number(Math.min(1, Math.max(0, scoreBase + (rand() - 0.5) * 0.4)).toFixed(2)),
    latencyMs: 380 + Math.round(rand() * 900),
  }))

const evalMaterialization = (
  version: AssetVersion,
  correctness: number,
  groundedness: number,
  inputVersionId: string,
): void => {
  materializations[version.versionId] = makeMaterialization(version, {
    inputVersionIds: [inputVersionId, dataset.versionId],
    costSeconds: 96,
    values: {
      scores: { type: 'metric', name: 'correctness', value: correctness, higherIsBetter: true },
      traces: {
        type: 'eval',
        datasetRef: 'support_qa/validation@240',
        sampleCount: 240,
        scores: { correctness, groundedness, refusal_rate: 0.07 },
        traces: traces(correctness),
      },
    },
    metrics: { correctness, groundedness },
  })
}

materializations[dataset.versionId] = makeMaterialization(dataset, {
  costSeconds: 4,
  values: {
    value: {
      type: 'frame',
      columns: ['id', 'question', 'reference', 'policy_clause'],
      dtypes: ['str', 'str', 'str', 'str'],
      rows: [
        ['q-100', 'Can I cancel within the first 14 days?', 'Yes, full refund.', '4.2'],
        ['q-101', 'Does the warranty cover water damage?', 'No.', '9.1'],
        ['q-102', 'How do I change the billing address?', 'Not covered by policy.', '—'],
      ],
      totalRows: 240,
    },
  },
})

for (const prompt of [promptV1, promptV2]) {
  materializations[prompt.versionId] = makeMaterialization(prompt, {
    values: { value: { type: 'note', markdown: prompt.definition.doc } },
  })
}

for (const [answers, seed] of [
  [answersHaiku, 3],
  [answersSonnet, 5],
] as const) {
  materializations[answers.versionId] = makeMaterialization(answers, {
    inputVersionIds: [dataset.versionId, promptV1.versionId],
    costSeconds: 128,
    values: {
      value: {
        type: 'frame',
        columns: ['id', 'answer', 'tokens', 'latency_ms'],
        dtypes: ['str', 'str', 'int64', 'int64'],
        rows: Array.from({ length: 4 }, (_, i) => [
          `q-${100 + i}`,
          `…answer ${i + seed}…`,
          64 + i * 11 + seed,
          420 + i * 63 + seed * 10,
        ]),
        totalRows: 240,
      },
    },
  })
}

evalMaterialization(evalBaseline, 0.71, 0.64, answersHaiku.versionId)
evalMaterialization(evalCited, 0.78, 0.86, answersHaiku.versionId)
evalMaterialization(evalSonnet, 0.84, 0.81, answersSonnet.versionId)

const baseSelection = {
  e_dataset: dataset.versionId,
  e_prompt: promptV1.versionId,
  e_answers: answersHaiku.versionId,
  e_eval: evalBaseline.versionId,
}

const branches: Record<string, Branch> = {
  main: {
    branchId: 'main',
    name: 'main',
    parentBranchId: null,
    forkedAtStep: 0,
    selection: baseSelection,
    pins: {},
    color: '#64748b',
    archived: false,
  },
  'prompt-cited': {
    branchId: 'prompt-cited',
    name: 'prompt/require-citations',
    parentBranchId: 'main',
    forkedAtStep: 8,
    selection: { ...baseSelection, e_prompt: promptV2.versionId, e_eval: evalCited.versionId },
    pins: { e_dataset: dataset.versionId },
    color: '#2563eb',
    archived: false,
  },
  'model-sonnet': {
    branchId: 'model-sonnet',
    name: 'model/sonnet-5',
    parentBranchId: 'main',
    forkedAtStep: 12,
    selection: {
      ...baseSelection,
      e_answers: answersSonnet.versionId,
      e_eval: evalSonnet.versionId,
    },
    pins: { e_dataset: dataset.versionId },
    color: '#0d9488',
    archived: false,
  },
}

const assets: Record<string, AssetVersion[]> = {}
for (const version of versions) {
  assets[version.assetId] = assets[version.assetId] ?? []
  assets[version.assetId].push(version)
}

/**
 * Work happens on the fork that asked for it, not all on `main`.
 *
 * A rail keyed on the branch a transaction landed in renders empty lanes if
 * every transaction claims the trunk, and the fork points carry no history.
 */
function branchForStep(step: number): string {
  if (step >= 12) return 'model-sonnet'
  if (step >= 8) return 'prompt-cited'
  return 'main'
}

function buildTransactions(): Transaction[] {
  const forked = new Set<string>(['main'])
  const transactions: Transaction[] = []

  versions.forEach((version, index) => {
    const branchId = branchForStep(version.createdAtStep)
    const ops: Transaction['ops'] = []

    if (!forked.has(branchId)) {
      forked.add(branchId)
      ops.push({
        op: 'fork-branch',
        branchId,
        fromBranchId: 'main',
        name: branches[branchId].name,
      })
    }
    ops.push({ op: 'create-asset', assetId: version.assetId, version })

    transactions.push({
      txId: `etx-${index}`,
      step: version.createdAtStep,
      branchId,
      author: version.authoredBy,
      intent: version.intent,
      ops,
      settled: version.definition.kind === 'eval',
    })
  })

  return transactions
}

export const llmEvalSession: FlowSession = {
  sessionId: 'session-llm-eval',
  name: 'support QA eval',
  projectName: 'support-assistant',
  scenario: 'llm-eval',
  createdAt: '2026-08-08T14:03:00Z',
  assets,
  materializations,
  branches,
  agents: {
    human: { agentId: 'human', label: 'You', color: '#0f172a', activeBranchId: 'main', activeAssetId: null },
    'agent-1': { agentId: 'agent-1', label: 'claude-1', color: '#2563eb', activeBranchId: 'prompt-cited', activeAssetId: 'e_prompt' },
    'agent-2': { agentId: 'agent-2', label: 'claude-2', color: '#0d9488', activeBranchId: 'model-sonnet', activeAssetId: 'e_answers' },
  },
  transactions: buildTransactions(),
  headBranchId: 'main',
}
