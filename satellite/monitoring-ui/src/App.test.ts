import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { Window } from '@/api/monitoring/interfaces'

const failures = vi.hoisted(() => ({ unauthorized: false }))

vi.mock('@/api/api.mock', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/api.mock')>()
  return {
    ...original,
    mockAdapter: async (config: InternalAxiosRequestConfig) => {
      if (failures.unauthorized) {
        throw new AxiosError('Unauthorized', AxiosError.ERR_BAD_REQUEST, config, null, {
          data: { detail: 'session expired' },
          status: 401,
          statusText: 'Unauthorized',
          headers: {},
          config,
        })
      }
      return original.mockAdapter(config)
    },
  }
})

vi.stubEnv('VITE_API_MOCK', 'true')

const WAIT = { timeout: 4000, interval: 25 }

const bodyText = () => document.body.textContent ?? ''

const waitForText = (text: string) => vi.waitFor(() => expect(bodyText()).toContain(text), WAIT)

const findButton = (text: string) =>
  Array.from(document.body.querySelectorAll<HTMLElement>('button, [role="tab"]')).find(
    (element) => element.textContent?.trim() === text,
  )

const click = async (text: string) => {
  const element = await vi.waitFor(() => {
    const found = findButton(text)
    expect(found, `button "${text}"`).toBeTruthy()
    return found as HTMLElement
  }, WAIT)
  element.click()
  await flushPromises()
}

describe('monitoring dashboard', () => {
  let wrapper: VueWrapper | null = null

  const mountApp = async () => {
    const [{ default: App }, { initPrimeVue }] = await Promise.all([
      import('./App.vue'),
      import('./lib/primevue'),
    ])
    const pinia = createPinia()
    setActivePinia(pinia)
    wrapper = mount(App, {
      attachTo: document.body,
      global: {
        plugins: [pinia, { install: initPrimeVue }],
        stubs: { MApexChart: true, transition: false },
      },
    })
    await flushPromises()
    return wrapper
  }

  beforeEach(async () => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
    failures.unauthorized = false
    localStorage.clear()
    const [{ resetMockState }, { resetSessionExpiredReport }] = await Promise.all([
      import('@/api/api.mock'),
      import('@/api/api.interceptors'),
    ])
    resetMockState()
    resetSessionExpiredReport()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('shows the deployment and the model-specific tabs', async () => {
    await mountApp()
    await waitForText('insurance-charges-regressor')
    await vi.waitFor(() => {
      expect(findButton('Data quality')).toBeTruthy()
      expect(findButton('Feature drift')).toBeTruthy()
    }, WAIT)
  })

  it('navigates between tabs', async () => {
    await mountApp()
    await click('Runtime')
    await waitForText('Latency p50')
    await click('Traces')
    await waitForText('evt-00001')
  })

  it('reloads the active section when a filter changes', async () => {
    const { api } = await import('@/api')
    const { useFiltersStore } = await import('@/store/filters')
    const getOverview = vi.spyOn(api.monitoring, 'getOverview')
    await mountApp()
    await vi.waitFor(() => expect(getOverview).toHaveBeenCalled(), WAIT)
    useFiltersStore().setWindow(Window.D30)
    await vi.waitFor(
      () =>
        expect(getOverview).toHaveBeenLastCalledWith(
          expect.objectContaining({ window: Window.D30 }),
        ),
      WAIT,
    )
  })

  it('opens a trace with its spans', async () => {
    await mountApp()
    await click('Traces')
    await click('evt-00001')
    await waitForText('model.predict')
  })

  it('acknowledges an alert from its dialog', async () => {
    const { api } = await import('@/api')
    const acknowledge = vi.spyOn(api.monitoring, 'acknowledgeAlert')
    await mountApp()
    await click('Alerts')
    await vi.waitFor(() => {
      const opener = document.body.querySelector<HTMLElement>('table tbody tr button')
      expect(opener).toBeTruthy()
      opener?.click()
    }, WAIT)
    await click('Acknowledge')
    await vi.waitFor(() => expect(acknowledge).toHaveBeenCalledTimes(1), WAIT)
    await vi.waitFor(() => expect(findButton('Acknowledged')).toBeTruthy(), WAIT)
  })

  it('replaces the dashboard with a notice when the session expires', async () => {
    failures.unauthorized = true
    await mountApp()
    await waitForText('Session expired')
  })
})
