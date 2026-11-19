import { EditorView } from '@codemirror/view'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, describe, expect, it } from 'vitest'
import CodePreview from '../CodePreview.vue'

enableAutoUnmount(afterEach)

const openFile = (fileName: string, textContent: string) =>
  mount(CodePreview, { props: { fileName, textContent }, global: { plugins: [PrimeVue] } })

function editor(wrapper: ReturnType<typeof openFile>): EditorView {
  return EditorView.findFromDOM(wrapper.get('.cm-content').element as HTMLElement)!
}

async function selectMode(wrapper: ReturnType<typeof openFile>, name: string) {
  const button = wrapper.findAll('button').find((button) => button.text() === name)
  expect(button).toBeDefined()
  await button!.trigger('click')
}

describe('code preview', () => {
  it('shows highlighted, selectable Python source in a read-only editor', () => {
    const source = 'def train():\n    return 42\n'
    const wrapper = openFile('TRAIN.PY', source)
    expect(editor(wrapper).state.doc.toString()).toBe(source)
    expect(editor(wrapper).state.readOnly).toBe(true)
    expect(wrapper.get('.cm-content').attributes('contenteditable')).toBe('false')
    expect(wrapper.get('.cm-content').attributes('aria-label')).toContain('TRAIN.PY')
    expect(wrapper.findAll('.cm-line span').map((span) => span.text())).toContain('def')
  })

  it.each(['log', 'txt'])('keeps .%s in a plain text preview', (ext) => {
    const wrapper = openFile(`run.${ext}`, 'def train():')
    expect(wrapper.get('pre code').text()).toBe('def train():')
    expect(wrapper.find('.cm-editor').exists()).toBe(false)
  })

  it('shows a read-only source view for code without a grammar', () => {
    const wrapper = openFile('build.sh', 'echo hello')
    expect(editor(wrapper).state.doc.toString()).toBe('echo hello')
    expect(editor(wrapper).state.readOnly).toBe(true)
  })

  it('renders Markdown locally and switches to highlighted raw Markdown', async () => {
    const source =
      '# Train\n\n![graph](https://example.com/chart.png) [report](https://example.com/report)'
    const wrapper = openFile('README.md', source)
    expect(wrapper.get('h1').text()).toBe('Train')
    expect(wrapper.get('img').attributes('src')).toBeUndefined()
    expect(wrapper.get('a').attributes('href')).toBe('https://example.com/report')
    await selectMode(wrapper, 'Raw')
    expect(editor(wrapper).state.doc.toString()).toBe(source)
    expect(wrapper.find('.cm-line span').exists()).toBe(true)
    await selectMode(wrapper, 'Rendered')
    expect(wrapper.get('h1').text()).toBe('Train')
  })

  it('keeps local diagrams and heading destinations in rendered Markdown', () => {
    const wrapper = openFile(
      'report.md',
      '<h2 id="chart">Chart</h2>\n\n[Chart](#chart)\n\n' +
        '<svg viewBox="0 0 10 10"><rect width="8" height="8" fill="red"/><circle fill="url(https://example.com/colors)"/></svg>',
    )
    expect(wrapper.get('a').attributes('href')).toBe('#chart')
    expect(wrapper.get('h2').attributes('id')).toBe('chart')
    expect(wrapper.get('svg rect').attributes('fill')).toBe('red')
    expect(wrapper.get('circle').attributes('fill')).toBeUndefined()
  })

  it.each(['? [a, b]\n: one', 'date: !!timestamp 2026-01-01'])(
    'offers Pretty for valid YAML %s',
    async (raw) => {
      const wrapper = openFile('report.yaml', raw)
      expect(wrapper.findAll('button').map((button) => button.text())).toContain('Pretty')
      await selectMode(wrapper, 'Raw')
      expect(editor(wrapper).state.doc.toString()).toBe(raw)
    },
  )

  it('strips external resources from embedded HTML in Markdown', () => {
    const source =
      '<style>div{color:red}</style><video src="https://example.com/a"></video>\n' +
      '<img srcset="https://example.com/b" style="background:url(https://example.com/c)" onerror="bad()">'
    const wrapper = openFile('README.md', source)
    expect(wrapper.find('.markdown-body style, .markdown-body video').exists()).toBe(false)
    expect(wrapper.find('[srcset], [onerror], .markdown-body [style]').exists()).toBe(false)
  })

  it.each([
    ['config.json', '{"n":9007199254740993,"n":2}', '{\n  "n": 9007199254740993,\n  "n": 2\n}'],
    [
      'params.yml',
      '{n: 9007199254740993, epochs: [1, 2]}',
      'n: 9007199254740993\nepochs:\n  - 1\n  - 2\n',
    ],
  ])(
    'formats %s without changing numeric literals, and keeps the original available',
    async (name, raw, pretty) => {
      const wrapper = openFile(name, raw)
      expect(editor(wrapper).state.doc.toString()).toBe(pretty)
      await selectMode(wrapper, 'Raw')
      expect(editor(wrapper).state.doc.toString()).toBe(raw)
      await selectMode(wrapper, 'Pretty')
      expect(editor(wrapper).state.doc.toString()).toBe(pretty)
    },
  )

  it.each([
    ['broken.json', '{"a":}'],
    ['broken.yaml', 'a: ['],
    ['duplicate.yaml', 'a: 1\na: 2'],
  ])('shows the raw %s and parse status without a toggle', (name, raw) => {
    const wrapper = openFile(name, raw)
    expect(editor(wrapper).state.doc.toString()).toBe(raw)
    expect(wrapper.get('[role="status"]').text()).toContain("Can't parse")
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('resets to the default mode on a file change and refreshes the displayed source', async () => {
    const wrapper = openFile('notes.md', '# First')
    await selectMode(wrapper, 'Raw')
    await wrapper.setProps({ fileName: 'config.json', textContent: '{"ok":true}' })
    expect(editor(wrapper).state.doc.toString()).toBe('{\n  "ok": true\n}')
    await wrapper.setProps({ textContent: '{"ok":false}' })
    expect(editor(wrapper).state.doc.toString()).toContain('false')
  })
})
