import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import { nextTick } from 'vue'
import FutureValuesEditor from '../FutureValuesEditor.vue'

type ChangeEvent = { complete: boolean; future: Record<string, string | number>[] }

const DATES = ['2024-01-01', '2024-02-01']

function mountEditor() {
  return mount(FutureValuesEditor, {
    props: { dates: DATES, columns: ['promo'], dateCol: 'date', frequency: 'month' as const },
  })
}

function lastChange(wrapper: VueWrapper): ChangeEvent {
  const events = wrapper.emitted('change') as ChangeEvent[][]
  return events[events.length - 1][0]
}

describe('FutureValuesEditor gating', () => {
  it('starts incomplete and keeps the completeness hint visible', () => {
    const wrapper = mountEditor()

    expect(lastChange(wrapper).complete).toBe(false)
    expect(wrapper.find('[data-testid="future-incomplete"]').exists()).toBe(true)
  })

  it('completes only once every cell holds a numeric value', async () => {
    const wrapper = mountEditor()

    await wrapper.find('[data-testid="cell-2024-01-01-promo"]').setValue('5')
    expect(lastChange(wrapper).complete).toBe(false)

    await wrapper.find('[data-testid="cell-2024-02-01-promo"]').setValue('8')
    await nextTick()

    const change = lastChange(wrapper)
    expect(change.complete).toBe(true)
    expect(change.future).toEqual([
      { date: '2024-01-01', promo: 5 },
      { date: '2024-02-01', promo: 8 },
    ])
    expect(wrapper.find('[data-testid="future-incomplete"]').exists()).toBe(false)
  })

  it('reverts to incomplete when a cell is cleared', async () => {
    const wrapper = mountEditor()
    await wrapper.find('[data-testid="cell-2024-01-01-promo"]').setValue('5')
    await wrapper.find('[data-testid="cell-2024-02-01-promo"]').setValue('8')
    expect(lastChange(wrapper).complete).toBe(true)

    await wrapper.find('[data-testid="cell-2024-02-01-promo"]').setValue('')
    expect(lastChange(wrapper).complete).toBe(false)
  })
})

describe('FutureValuesEditor CSV fill', () => {
  it('matches uploaded rows to the horizon dates by period and fills the grid', async () => {
    const wrapper = mountEditor()

    // dates within the same month as the horizon still match (period-based)
    ;(wrapper.vm as unknown as { applyRecords: (r: unknown[]) => void }).applyRecords([
      { date: '2024-01-20', promo: 3 },
      { date: '2024-02-15', promo: 7 },
    ])
    await nextTick()

    const change = lastChange(wrapper)
    expect(change.complete).toBe(true)
    expect(change.future).toEqual([
      { date: '2024-01-01', promo: 3 },
      { date: '2024-02-01', promo: 7 },
    ])
  })

  it('ignores CSV rows whose dates fall outside the horizon', async () => {
    const wrapper = mountEditor()

    ;(wrapper.vm as unknown as { applyRecords: (r: unknown[]) => void }).applyRecords([
      { date: '2024-01-05', promo: 3 },
      { date: '2025-09-01', promo: 99 },
    ])
    await nextTick()

    const change = lastChange(wrapper)
    expect(change.complete).toBe(false)
    expect(wrapper.find('[data-testid="cell-2024-02-01-promo"]').element.value).toBe('')
  })
})
