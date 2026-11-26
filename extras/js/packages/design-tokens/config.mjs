import { fileURLToPath } from 'node:url'
import StyleDictionary from 'style-dictionary'

export const root = fileURLToPath(new URL('./', import.meta.url))

StyleDictionary.registerTransform({
  name: 'name/cti/kebab-prefixed',
  type: 'name',
  transform: (token) => `p-${token.path.join('-')}`,
})

StyleDictionary.registerTransform({
  name: 'value/px',
  type: 'value',
  filter: (token) => token['$type'] === 'number',
  transform: (token) => {
    if (token.path[token.path.length - 1] === 'weight') {
      return token['$value']
    } else if (token.path[token.path.length - 1] === 'opacity') {
      return token['$value'] / 100
    }

    return `${token['$value']}px`
  },
})

StyleDictionary.registerTransform({
  name: 'value/boxShadow',
  type: 'value',
  filter: (token) => token['$type'] === 'boxShadow',
  transform: (token) => {
    const shadow = token.original['$value']
    if (Array.isArray(shadow)) {
      const shadowValues = shadow.map((s) => {
        const { color, x, y, blur, spread } = s
        return `${x}px ${y}px ${blur}px ${spread}px ${color}`
      })
      return shadowValues.join(', ')
    } else {
      const { color, x, y, blur, spread } = shadow
      return `${x}px ${y}px ${blur}px ${spread}px ${color}`
    }
  },
})

StyleDictionary.registerTransformGroup({
  name: 'custom/css',
  transforms: ['name/cti/kebab-prefixed', 'value/px', 'value/boxShadow'],
})

export const themes = [
  { name: 'light', selector: 'body' },
  { name: 'dark', selector: "[data-theme='dark'] body" },
]

export const createThemeDictionary = ({ name, selector }) =>
  new StyleDictionary({
    log: { errors: { brokenReferences: 'console' } },
    source: [`${root}tokens/tokens-styles-${name}.json`],
    platforms: {
      css: {
        transformGroup: 'custom/css',
        buildPath: root,
        files: [
          {
            destination: `${name}-theme.css`,
            format: 'css/variables',
            options: { selector },
            filter: (token) => !String(token.$value).includes('{'),
          },
        ],
      },
    },
  })
