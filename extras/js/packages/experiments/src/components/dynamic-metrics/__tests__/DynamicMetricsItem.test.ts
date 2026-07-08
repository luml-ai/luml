import { describe, it, expect, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import DynamicMetricsItem from '../DynamicMetricsItem.vue'
import { ThemeKey } from '@/lib/theme/ThemeProvider'
import type { ExperimentSnapshotDynamicMetric, ModelInfo } from '@/interfaces/interfaces'

const { newPlotMock } = vi.hoisted(() => ({ newPlotMock: vi.fn() }))

vi.mock('@/services/PlotlyService', () => ({
  plotlyService: {
    getPlotly: vi.fn(async () => ({
      newPlot: newPlotMock,
      relayout: vi.fn(),
      Plots: { resize: vi.fn() },
    })),
  },
}))

// Render the card's default slot so the chart container ref resolves.
const contentStub = { template: '<div><slot /></div>' }

async function mountChart(
  data: ExperimentSnapshotDynamicMetric[],
  modelsInfo: Record<string, ModelInfo>,
) {
  const wrapper = mount(DynamicMetricsItem, {
    props: { metricName: 'loss', data, modelsInfo },
    global: {
      provide: { [ThemeKey]: ref('light') },
      stubs: { DynamicMetricsItemContent: contentStub },
    },
  })
  await flushPromises()
  return wrapper
}

function tracesFromLastRender() {
  expect(newPlotMock).toHaveBeenCalled()
  const lastCall = newPlotMock.mock.calls.at(-1)
  return lastCall![1] as Array<Record<string, unknown>>
}

describe('DynamicMetricsItem trace config', () => {
  it('renders a linear line with no smoothing and the exact logged values', async () => {
    const data: ExperimentSnapshotDynamicMetric[] = [
      { modelId: 'm1', x: [1, 2, 3], y: [0, 10, 0], aggregated: false },
    ]
    const modelsInfo: Record<string, ModelInfo> = { m1: { name: 'Model A', color: '#123456' } }

    await mountChart(data, modelsInfo)

    const traces = tracesFromLastRender()
    expect(traces).toHaveLength(1)

    const trace = traces[0]
    const line = trace.line as Record<string, unknown>
    expect(line.shape).toBe('linear')
    expect(line).not.toHaveProperty('smoothing')

    // The plotted points are exactly the logged points — no interpolated
    // overshoot can exceed the [0, 10] range of the input.
    expect(trace.x).toEqual([1, 2, 3])
    expect(trace.y).toEqual([0, 10, 0])
    expect(trace.mode).toBe('lines')
  })
})
