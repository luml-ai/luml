import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import NotebooksModelsTable from './NotebooksModelsTable.vue'

vi.mock('primevue', async () => {
  const { defineComponent, h, inject, provide } = await import('vue')
  const rows = Symbol('rows')

  return {
    DataTable: defineComponent({
      props: { value: { type: Array, default: () => [] } },
      setup: (props, { slots }) => {
        provide(rows, props)
        return () => h('div', slots.default?.())
      },
    }),
    Column: defineComponent({
      props: { field: String },
      setup: (props, { slots }) => {
        const table = inject<{ value: Array<{ size: number }> }>(rows, { value: [] })
        return () =>
          props.field === 'size'
            ? h(
                'div',
                table.value.map((data) =>
                  h('span', { class: 'model-size' }, slots.body?.({ data })),
                ),
              )
            : null
      },
    }),
  }
})

describe('NotebooksModelsTable model sizes', () => {
  it('displays bytes, kilobytes, and correct megabytes at and above the boundary', () => {
    const wrapper = mount(NotebooksModelsTable, {
      props: {
        files: [999, 1000, 1000000, 12345678].map((size) => ({
          name: 'model',
          size,
          created: '2026-01-01',
        })),
      },
      global: { stubs: { NotebooksModelAction: true } },
    })

    expect(wrapper.findAll('.model-size').map((cell) => cell.text())).toEqual([
      '999.00 B',
      '1.00 KB',
      '1.00 MB',
      '12.35 MB',
    ])
  })
})
