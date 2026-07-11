import pluginVue from 'eslint-plugin-vue'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,mts,tsx,vue}'],
  },

  {
    name: 'app/files-to-ignore',
    ignores: [
      '**/dist/**',
      '**/dist-ssr/**',
      '**/coverage/**',
      '**/.storybook/**',
      '**/tests/**',
      '**/__tests__/**',
      'public/**',
      'eslint.config.js',
      'style-dictionary.config.mjs',
      'src/stories/**',
      'playwright-report/**',
    ],
  },

  pluginVue.configs['flat/essential'],
  vueTsConfigs.strict,
  skipFormatting,

  {
    name: 'app/component-name-exceptions',
    files: ['**/index.vue', '**/Navigation.vue', '**/Toolbar.vue', '**/Ui404.vue', 'src/main.ts'],
    rules: {
      'vue/multi-word-component-names': 'off',
    },
  },

  {
    languageOptions: {
      parserOptions: {
        tsconfigRootDir: __dirname,
      },
    },
  },
)
