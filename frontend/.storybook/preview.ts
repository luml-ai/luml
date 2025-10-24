import type { Preview } from '@storybook/vue3'
import { setup } from '@storybook/vue3'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import { dPreset } from '../src/lib/primevue/preset'
import { vueRouter } from 'storybook-vue3-router'
import '../src/assets/main.css'
import '../src/assets/tables.css'

if (typeof window !== 'undefined') {
  window.axios = {
    get: () => Promise.resolve({ data: [] }),
    post: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }),
  }
}

const pinia = createPinia()

setup((app) => {
  app.use(pinia)
  app.use(PrimeVue, {
    theme: {
      preset: dPreset,
      options: { darkModeSelector: '[data-theme="dark"]' },
    },
  })
  app.use(ToastService)
})

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    backgrounds: {
      default: 'light',
      values: [
        { name: 'light', value: '#F8FAFC' },
        { name: 'dark', value: '#1a1a1a' },
      ],
    },
    layout: 'fullscreen',
  },
  globalTypes: {
    theme: {
      description: 'Global theme for components',
      defaultValue: 'light',
      toolbar: {
        title: 'Theme',
        icon: 'circlehollow',
        items: ['light', 'dark'],
        dynamicTitle: true,
      },
    },
  },
  decorators: [
    vueRouter([
      { path: '/', name: 'home' },
      { path: '/sign-in', name: 'sign-in' },
      { path: '/sign-up', name: 'sign-up' },
      { path: '/runtime', name: 'runtime' },
      { path: '/notebooks', name: 'notebooks' },
      { path: '/data-agent', name: 'data-agent' },
      { path: '/model', name: 'model' },
      { path: '/model-card', name: 'model-card' },
      { path: '/model-snapshot', name: 'model-snapshot' },
      { path: '/organization/:id', name: 'organization' },
      { path: '/organizations/:organizationId/orbits', name: 'orbits' },
      { path: '/organizations/:organizationId/orbit/:orbitId', name: 'orbit' },
      { path: '/organizations/:organizationId/collection/:collectionId', name: 'collection' },
      { path: '/:pathMatch(.*)*', name: 'not-found' },
    ]),
    (story, context) => {
      const theme = context.globals.theme || 'light'
      if (typeof document !== 'undefined') {
        document.documentElement.setAttribute('data-theme', theme)
      }
      return { components: { story }, template: '<story />' }
    },
  ],
}

export default preview
