import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ConsoleView from '@/flow/workbench/components/card/ConsoleView.vue'
import LogsView from '@/flow/workbench/components/card/LogsView.vue'
import RendererHost from '@/flow/workbench/renderers/RendererHost.vue'
import type { BlocksPreview, FramePreview, NotePreview } from '@/flow/workbench/model/types'

describe('flow value renderers', () => {
  it('reports both visible and total columns in a wide frame footer', () => {
    const preview: FramePreview = {
      type: 'frame',
      columns: Array.from({ length: 40 }, (_, index) => `column_${index}`),
      dtypes: Array.from({ length: 40 }, () => 'float64'),
      rows: [Array.from({ length: 40 }, (_, index) => index)],
      totalRows: 1,
      totalColumns: 200,
    }
    const wrapper = mount(RendererHost, { props: { preview } })

    expect(wrapper.text()).toContain('1 of 1 rows')
    expect(wrapper.text()).toContain('40 of 200 columns')
  })

  it('renders a non-finite metric token and a small metric without inventing absent keys', () => {
    const measured: BlocksPreview = {
      type: 'blocks',
      kind: 'metric',
      blocks: [{ block: 'kv', entries: { loss: 'nan', auc: 0.00032 } }],
    }
    const absent: BlocksPreview = {
      type: 'blocks',
      kind: 'metric',
      blocks: [{ block: 'kv', entries: { auc: 0.75 } }],
    }
    const measuredWrapper = mount(RendererHost, { props: { preview: measured } })
    const absentWrapper = mount(RendererHost, { props: { preview: absent } })

    expect(measuredWrapper.text()).toContain('lossnan')
    expect(measuredWrapper.text()).toContain('auc3.2e-4')
    expect(absentWrapper.findAll('dt').map((entry) => entry.text())).toEqual(['auc'])
    expect(absentWrapper.text()).not.toContain('loss')
  })

  it('strips ANSI and applies carriage returns in live and stored logs', () => {
    const update = '\u001b[31m10%\u001b[0m\r\u001b[32m20%\u001b[0m'
    const consoleView = mount(ConsoleView, { props: { lines: [update] } })
    const logsView = mount(LogsView, { props: { logs: update } })

    for (const wrapper of [consoleView, logsView]) {
      expect(wrapper.text()).toContain('20%')
      expect(wrapper.text()).not.toContain('10%')
      expect(wrapper.text()).not.toContain('\u001b')
    }
  })

  it('removes interactive markup, styles, and remote images from notes', () => {
    const preview: NotePreview = {
      type: 'note',
      markdown: [
        '<style>.markdown-body { display: none }</style>',
        '',
        '<form><input value="secret"><button>send</button></form>',
        '',
        '![remote](https://example.com/tracker.png)',
        '',
        '![local](/images/chart.png)',
      ].join('\n'),
    }
    const wrapper = mount(RendererHost, { props: { preview } })

    expect(wrapper.find('style').exists()).toBe(false)
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.find('input').exists()).toBe(false)
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.find('img[src="https://example.com/tracker.png"]').exists()).toBe(false)
    expect(wrapper.find('img[src="/images/chart.png"]').exists()).toBe(true)
  })
})
