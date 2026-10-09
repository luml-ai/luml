import { shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { Position, type EdgeProps } from '@vue-flow/core'
import CustomArrowEdge from '../CustomArrowEdge.vue'

vi.mock('@vue-flow/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@vue-flow/core')>()
  return {
    ...actual,
    getSmoothStepPath: () => ['M0 0L100 0', 0, 0, 0, 0],
    useVueFlow: () => ({
      findNode: () => undefined,
      getSelectedEdges: { value: [] },
    }),
  }
})

const BaseEdgeStub = defineComponent({
  name: 'BaseEdge',
  props: {
    path: { type: String, required: true },
    markerStart: { type: String, required: true },
    markerEnd: { type: String, required: true },
  },
  template: '<path :data-marker-start="markerStart" :data-marker-end="markerEnd" />',
})

function edgeProps(): EdgeProps {
  return {
    id: 'source-target',
    source: 'source',
    target: 'target',
    sourceNode: {} as EdgeProps['sourceNode'],
    targetNode: {} as EdgeProps['targetNode'],
    sourceX: 0,
    sourceY: 0,
    targetX: 100,
    targetY: 0,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    type: 'custom',
    markerStart: '',
    markerEnd: '',
    data: {},
    events: {},
  }
}

describe('CustomArrowEdge', () => {
  it('renders the arrow marker at the target end', () => {
    const wrapper = shallowMount(CustomArrowEdge, {
      props: edgeProps(),
      global: {
        stubs: {
          BaseEdge: BaseEdgeStub,
          CustomArrowMarker: true,
        },
      },
    })

    expect(wrapper.find('path').attributes()).toMatchObject({
      'data-marker-start': 'url(#source-target-marker)',
      'data-marker-end': 'url(#source-target-marker-arrow)',
    })
  })
})
