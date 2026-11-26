import { createThemeDictionary, themes } from './config.mjs'

for (const theme of themes) {
  await createThemeDictionary(theme).buildAllPlatforms()
}
