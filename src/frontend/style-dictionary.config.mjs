import StyleDictionary from 'style-dictionary'

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

export default {
  source: ['tokens/tokens-styles-light.json'], // for light
  // source: ['tokens/tokens-styles-dark.json'], // for dark
  platforms: {
    light: {
      transformGroup: 'custom/css',
      buildPath: 'src/assets/theme/',
      files: [
        {
          destination: 'light-theme.css',
          format: 'css/variables',
          options: {
            selector: 'body',
          },
          filter: (token) => token.filePath.includes('light'),
        },
      ],
    },
    dark: {
      transformGroup: 'custom/css',
      buildPath: 'src/assets/theme/',
      files: [
        {
          destination: 'dark-theme.css',
          format: 'css/variables',
          options: {
            selector: "[data-theme='dark'] body",
          },
          filter: (token) => token.filePath.includes('dark'),
        },
      ],
    },
  },
}
