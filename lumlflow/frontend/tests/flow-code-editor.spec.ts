
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import type { CodeEditorHandle } from '@/flow/workbench/components/card/codeMirror'
import SourceEditor from '@/flow/workbench/components/card/SourceEditor.vue'
import { editorIn, press } from './editor'

const TAB = 9
const ENTER = 13
const ESCAPE = 27

const SOURCE = `class TrainXGB:
    """Train the churn model."""
    params = {"lr": 3e-4, "epochs": 24}

    def materialize(self, ctx, train):
        return {"model": train_xgb(train, lr=self.params["lr"])}
`

async function editing(
  source = SOURCE,
  props: { readonly?: boolean } = {},
): Promise<{ wrapper: VueWrapper; handle: CodeEditorHandle }> {
  const wrapper = mount(SourceEditor, { props: { modelValue: source, ...props } })
  return { wrapper, handle: await editorIn(wrapper) }
}

describe('the cell source editor', () => {
  it('opens on the source it was handed, with gutter and highlighting', async () => {
    const { wrapper, handle } = await editing()

    expect(handle.view.state.doc.toString()).toBe(SOURCE)
    expect(wrapper.find('.cm-editor').exists()).toBe(true)
    expect(wrapper.find('.cm-lineNumbers').exists()).toBe(true)
    expect(wrapper.findAll('.cm-line span').length).toBeGreaterThan(0)
    expect(wrapper.find('pre').exists()).toBe(false)
    wrapper.unmount()
  })

  it('round-trips what is typed into it', async () => {
    const { wrapper, handle } = await editing()

    handle.view.dispatch({
      changes: { from: handle.view.state.doc.length, insert: '    seed = 1337\n' },
    })
    await wrapper.vm.$nextTick()

    const updates = wrapper.emitted('update:modelValue')
    expect(updates).toBeTruthy()
    expect(updates!.at(-1)![0]).toBe(`${SOURCE}    seed = 1337\n`)
    wrapper.unmount()
  })

  it('takes a new document from above without echoing it back as an edit', async () => {
    const { wrapper, handle } = await editing()

    await wrapper.setProps({ modelValue: 'class Features:\n    pass\n' })

    expect(handle.view.state.doc.toString()).toBe('class Features:\n    pass\n')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    wrapper.unmount()
  })

  it('renders read-only source the same way and refuses to take any', async () => {
    const { wrapper, handle } = await editing(SOURCE, { readonly: true })

    expect(handle.view.state.doc.toString()).toBe(SOURCE)
    expect(wrapper.find('.cm-lineNumbers').exists()).toBe(true)
    expect(handle.view.contentDOM.getAttribute('contenteditable')).toBe('false')

    expect(handle.view.state.readOnly).toBe(true)
    wrapper.unmount()
  })

  it('unlocks when the surface stops being read-only', async () => {
    const { wrapper, handle } = await editing(SOURCE, { readonly: true })

    await wrapper.setProps({ readonly: false })

    expect(handle.view.state.readOnly).toBe(false)
    expect(handle.view.contentDOM.getAttribute('contenteditable')).toBe('true')
    wrapper.unmount()
  })

  it('indents the next line the way Python would', async () => {
    const { wrapper, handle } = await editing('def materialize(self, ctx):')
    handle.view.dispatch({ selection: { anchor: handle.view.state.doc.length } })

    press(handle, 'Enter', ENTER)

    expect(handle.view.state.doc.toString()).toBe('def materialize(self, ctx):\n    ')
    wrapper.unmount()
  })

  it('takes Tab for indentation, and gives it back after Escape', async () => {
    const { wrapper, handle } = await editing('x = 1\n')

    press(handle, 'Tab', TAB)
    expect(handle.view.state.doc.toString()).toBe('    x = 1\n')

    press(handle, 'Escape', ESCAPE)
    press(handle, 'Tab', TAB)
    expect(handle.view.state.doc.toString()).toBe('    x = 1\n')
    wrapper.unmount()
  })
})
