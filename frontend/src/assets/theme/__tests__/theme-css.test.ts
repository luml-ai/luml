// @vitest-environment node

import { readFile } from 'node:fs/promises'
import StyleDictionary from 'style-dictionary'
import { describe, expect, it } from 'vitest'
import config from '../../../../style-dictionary.config.mjs'

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
  it('resolves form-field focus-ring lengths without changing other lengths', async () => {
    const dictionary = new StyleDictionary({
      ...config,
      source: [`tokens/tokens-styles-${theme}.json`],
    })
    const [file] = await dictionary.formatPlatform(theme)
    const css = file.output as string

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

  it('ships CSS without invalid object values', async () => {
    const css = await readFile(`src/assets/theme/${theme}-theme.css`, 'utf8')

    expect(css).not.toContain('[object Object]')
    for (const component of components) {
      expect(css).toContain(`--p-${component}-focus-ring-width: 0px;`)
      expect(css).toContain(`--p-${component}-focus-ring-offset: 0px;`)
    }
  })
})
