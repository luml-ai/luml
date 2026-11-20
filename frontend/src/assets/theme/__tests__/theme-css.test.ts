// @vitest-environment node

import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { describe, expect, it } from 'vitest'

const require = createRequire(import.meta.url)

const components = [
  'autocomplete',
  'inputtext',
  'cascadeselect',
  'select',
  'textarea',
  'multiselect',
  'treeselect',
]

describe.each(['light', 'dark'])('%s theme CSS', (theme) => {
  it('ships form-field focus-ring lengths without invalid object values', async () => {
    const css = await readFile(require.resolve(`@luml/design-tokens/${theme}-theme.css`), 'utf8')

    expect(css).not.toContain('[object Object]')
    for (const component of components) {
      expect(css).toContain(`--p-${component}-focus-ring-width: 0px;`)
      expect(css).toContain(`--p-${component}-focus-ring-offset: 0px;`)
    }
    expect(css).toContain('--p-focus-ring-width: 1px;')
    expect(css).toContain('--p-focus-ring-offset: 2px;')
    expect(css).toContain('--p-button-focus-ring-width: 1px;')
    expect(css).toContain('--p-button-focus-ring-offset: 2px;')
    expect(css).toContain('--p-tabs-tab-focus-ring-offset: -1px;')
  })
})
