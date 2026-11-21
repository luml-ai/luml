// @vitest-environment node

import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { createThemeDictionary, themes } from '@luml/design-tokens/config.mjs'
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

const declarations = (css: string) =>
  Object.fromEntries(
    [...css.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map(([, name, value]) => [
      name,
      (value ?? '').replace(/\s+/g, ' ').trim(),
    ]),
  )

const generate = async (name: string) => {
  const theme = themes.find((item: { name: string }) => item.name === name)
  if (!theme) {
    throw new Error(`Theme ${name} not found`)
  }
  const [file] = await createThemeDictionary(theme).formatPlatform('css')
  return file.output as string
}

describe.each(['light', 'dark'])('%s theme CSS', (theme) => {
  it('generates form-field focus-ring lengths without invalid object values', async () => {
    const css = await generate(theme)

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

  it('ships CSS that matches the generator output', async () => {
    const shipped = await readFile(
      require.resolve(`@luml/design-tokens/${theme}-theme.css`),
      'utf8',
    )

    expect(declarations(shipped)).toEqual(declarations(await generate(theme)))
  })
})
