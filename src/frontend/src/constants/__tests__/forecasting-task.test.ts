import { describe, it, expect } from 'vitest'
import { availableTasks, forecastingSteps } from '../constants'
import router from '@/router'

const forecastingCard = availableTasks.find((task) => task.title === 'Time Series Forecasting')

describe('forecasting task card', () => {
  it('is enabled and linked to the forecasting route', () => {
    expect(forecastingCard).toBeDefined()
    expect(forecastingCard?.isDisabled).toBeFalsy()
    expect(forecastingCard?.btnText).toBe('next')
    expect(forecastingCard?.linkName).toBe('forecasting')
    expect(forecastingCard?.analyticsTaskName).toBe('forecasting')
  })

  it('offers training only — no inference dropdown', () => {
    expect(forecastingCard?.dropdownOptions).toBeUndefined()
  })

  it('exposes the three forecasting step labels', () => {
    expect(forecastingSteps.map((step) => step.text)).toEqual([
      'Data Upload',
      'Forecast Setup',
      'Model Evaluation',
    ])
  })
})

describe('forecasting route', () => {
  it('resolves /forecasting to a named route with the tabular invalid-message guard', () => {
    expect(router.hasRoute('forecasting')).toBe(true)

    const resolved = router.resolve({ name: 'forecasting' })
    expect(resolved.path).toBe('/forecasting')
    expect(resolved.meta.showInvalidMessage).toBe(992)
  })
})
