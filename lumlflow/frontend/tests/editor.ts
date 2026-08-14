/**
 * Reaching the mounted CodeMirror inside a surface under test.
 *
 * The editor fetches itself, so the wait is on real ticks rather than a
 * microtask flush — and it is a wait rather than a mock on purpose: stubbing the
 * import out would leave the specs asserting against a wrapper nobody ships.
 */

import { nextTick } from 'vue'
import type { VueWrapper } from '@vue/test-utils'

import type { CodeEditorHandle } from '@/flow/workbench/components/card/codeMirror'
import SourceEditor from '@/flow/workbench/components/card/SourceEditor.vue'

export async function editorIn(wrapper: VueWrapper): Promise<CodeEditorHandle> {
  for (let tries = 0; tries < 200; tries += 1) {
    const found = wrapper.findComponent(SourceEditor)
    const handle = found.exists()
      ? (found.vm as unknown as { editor: CodeEditorHandle | null }).editor
      : null
    if (handle) return handle
    await new Promise((done) => setTimeout(done, 0))
    await nextTick()
  }
  throw new Error('the code editor never mounted')
}

/** A keystroke as the editor sees one — CodeMirror reads both name and code. */
export function press(handle: CodeEditorHandle, key: string, keyCode: number): void {
  handle.view.contentDOM.dispatchEvent(
    new KeyboardEvent('keydown', { key, keyCode, bubbles: true, cancelable: true }),
  )
}
