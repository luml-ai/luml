import { afterEach, describe, expect, it, vi } from 'vitest'

const plotlyModule = vi.hoisted(() => ({ fail: true }))

vi.mock('plotly.js-dist', () => {
  if (plotlyModule.fail) throw new Error('chunk failed')
  return { default: { react: () => {} } }
})

async function freshService() {
  vi.resetModules()
  return (await import('../PlotlyService')).plotlyService
}

afterEach(() => {
  plotlyModule.fail = true
})

describe('PlotlyService', () => {
  it('swallows a failed preload and loads again when a chart asks', async () => {
    const unhandled = vi.fn()
    process.on('unhandledRejection', unhandled)
    try {
      const service = await freshService()
      service.preload()
      await new Promise((resolve) => setTimeout(resolve, 0))
      expect(unhandled).not.toHaveBeenCalled()
      await expect(service.getPlotly()).rejects.toThrow()

      plotlyModule.fail = false
      await expect(service.getPlotly()).resolves.toHaveProperty('react')
    } finally {
      process.off('unhandledRejection', unhandled)
    }
  })

  it('shares one load between the preload and the charts', async () => {
    plotlyModule.fail = false
    const service = await freshService()
    service.preload()
    const loading = service.getPlotly()

    expect(service.getPlotly()).toBe(loading)
    await expect(loading).resolves.toHaveProperty('react')
  })
})
