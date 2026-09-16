import { onBeforeUnmount, watch, type Ref } from 'vue'
import { loadPlotly } from '@/plotly/plotly'

const PLOTLY_CONFIG = { displayModeBar: false, responsive: true }

export function usePlotlyChart(
  container: Ref<HTMLElement | null>,
  data: () => Record<string, unknown>[],
  layout: () => Record<string, unknown>,
) {
  let plotted = false

  async function render() {
    const node = container.value
    if (!node) return
    const Plotly = await loadPlotly()
    if (container.value !== node) return
    if (plotted) {
      await Plotly.react(node, data(), layout(), PLOTLY_CONFIG)
    } else {
      await Plotly.newPlot(node, data(), layout(), PLOTLY_CONFIG)
      plotted = true
    }
  }

  watch([container, data, layout], render, { immediate: true, deep: true })

  onBeforeUnmount(() => {
    const node = container.value
    if (node) void loadPlotly().then((Plotly) => Plotly.purge(node))
  })
}
