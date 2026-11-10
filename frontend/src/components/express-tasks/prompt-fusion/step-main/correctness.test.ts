import { flushPromises, shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Position } from '@vue-flow/core'
import Sidebar from './sidebar/index.vue'
import PresentationArea from './PresentationArea.vue'
import Optimization from './control-center/optimization/index.vue'
import { NodeTypeEnum } from '../interfaces'
import { EvaluationModesEnum } from '@/lib/promt-fusion/prompt-fusion.interfaces'

const mocks = vi.hoisted(() => ({
  removeEdges: vi.fn(),
  track: vi.fn(),
  service: {
    taskDescription: '',
    teacherModel: 'teacher',
    studentModel: 'student',
    evaluationMode: 'None',
    runOptimization: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
  },
}))
vi.mock('@vue-flow/core', async (original) => ({
  ...(await original<typeof import('@vue-flow/core')>()),
  useVueFlow: () => ({
    nodes: ref([]),
    getEdges: ref([]),
    getSelectedEdges: ref([{ id: 'edge-1' }]),
    removeEdges: mocks.removeEdges,
    onConnect: vi.fn(),
    addEdges: vi.fn(),
    removeNodes: vi.fn(),
    addNodes: vi.fn(),
    toObject: vi.fn(),
  }),
}))
vi.mock('@/lib/promt-fusion/PromptFusionService', () => ({ promptFusionService: mocks.service }))
vi.mock('@/lib/analytics/AnalyticsService', () => ({
  AnalyticsService: { track: mocks.track },
  AnalyticsTrackKeysEnum: { run_optimization: 'run_optimization' },
}))
vi.mock('primevue', async (original) => ({
  ...(await original<typeof import('primevue')>()),
  useConfirm: () => ({ require: vi.fn() }),
  useToast: () => ({ add: vi.fn() }),
}))
afterEach(() => {
  document.body.innerHTML = ''
})
describe('prompt fusion UI correctness', () => {
  it('flags duplicate input and output names independently', () => {
    const wrapper = shallowMount(Sidebar, {
      props: {
        data: {
          label: 'Processor',
          icon: 'cpu',
          iconColor: 'var(--p-primary-color)',
          showMenu: false,
          type: NodeTypeEnum.processor,
          fields: [
            { id: 'i1', value: 'same', variant: 'input', handlePosition: Position.Left },
            { id: 'i2', value: 'same', variant: 'input', handlePosition: Position.Left },
            { id: 'o1', value: 'duplicate', variant: 'output', handlePosition: Position.Right },
            { id: 'o2', value: 'duplicate', variant: 'output', handlePosition: Position.Right },
          ],
        },
      },
    })
    const fields = wrapper.findAllComponents({ name: 'BaseField' })
    expect(fields).toHaveLength(4)
    expect(fields.every((field) => field.props('isDuplicate'))).toBe(true)
    wrapper.unmount()
  })
  it.each([
    ['input', ''],
    ['textarea', ''],
    ['select', ''],
    ['div', 'contenteditable="true"'],
    ['span', ''],
  ])('preserves edges while deleting text in %s %s', async (tag, attrs) => {
    const wrapper = shallowMount(PresentationArea, { props: { initialNodes: [] } })
    const editable = document.createElement('div')
    editable.innerHTML =
      tag === 'span'
        ? '<div contenteditable="true"><span>text</span></div>'
        : `<${tag} ${attrs}></${tag}>`
    document.body.append(editable)
    editable
      .querySelector(tag)
      ?.dispatchEvent(new KeyboardEvent('keydown', { code: 'Delete', bubbles: true }))
    expect(mocks.removeEdges).not.toHaveBeenCalled()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { code: 'Delete', bubbles: true }))
    expect(mocks.removeEdges).toHaveBeenCalledWith([{ id: 'edge-1' }])
    wrapper.unmount()
    mocks.removeEdges.mockClear()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { code: 'Delete', bubbles: true }))
    expect(mocks.removeEdges).not.toHaveBeenCalled()
  })
  it.each([
    [EvaluationModesEnum.exactMatch, 'exact_match'],
    [EvaluationModesEnum.llmBased, 'llm_based'],
    [EvaluationModesEnum.none, 'none'],
  ])('reports the selected evaluation mode %s', async (mode, expected) => {
    mocks.service.evaluationMode = mode
    const wrapper = shallowMount(Optimization, { props: { disabled: false } })
    await (wrapper.vm as unknown as { runOptimization: () => Promise<void> }).runOptimization()
    await flushPromises()
    expect(mocks.track).toHaveBeenCalledWith(
      'run_optimization',
      expect.objectContaining({ evaluation_metrics: expected }),
    )
    wrapper.unmount()
  })
})
