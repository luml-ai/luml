import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import type { MenuItem } from 'primevue/menuitem'
import ForecastColumnHeader from '../ForecastColumnHeader.vue'
import type { ForecastColumnRole } from '@/hooks/useForecastSetup'

const MenuStub = {
  name: 'Menu',
  props: ['model', 'popup'],
  template: '<div />',
  methods: { toggle: () => {} },
}

const DButton = {
  name: 'DButton',
  emits: ['click'],
  template: '<button @click="$emit(\'click\', $event)"><slot name="icon" /></button>',
}

function mountHeader(role: ForecastColumnRole, column = 'sales') {
  return mount(ForecastColumnHeader, {
    props: { column, columnType: 'number' as const, role },
    global: {
      components: { DButton },
      stubs: { Menu: MenuStub },
      directives: { tooltip: {} },
    },
  })
}

function menuLabels(wrapper: ReturnType<typeof mountHeader>): string[] {
  const model = wrapper.findComponent({ name: 'Menu' }).props('model') as MenuItem[]
  return model.map((item) => String(item.label))
}

function runCommand(wrapper: ReturnType<typeof mountHeader>, label: string) {
  const model = wrapper.findComponent({ name: 'Menu' }).props('model') as MenuItem[]
  const item = model.find((entry) => entry.label === label)
  item?.command?.({ originalEvent: new Event('click'), item })
}

describe('ForecastColumnHeader menu', () => {
  it('offers date, target and auxiliary actions for an unassigned column', () => {
    const wrapper = mountHeader(null)
    expect(menuLabels(wrapper)).toEqual(['Set as date column', 'Set as target', 'Set as auxiliary'])
  })

  it('offers only the opposite role for the date and target columns', () => {
    expect(menuLabels(mountHeader('date'))).toEqual(['Set as target'])
    expect(menuLabels(mountHeader('target'))).toEqual(['Set as date column'])
  })

  it('emits the swap events from the date and target column menus', () => {
    const dateWrapper = mountHeader('date')
    runCommand(dateWrapper, 'Set as target')
    expect(dateWrapper.emitted('setTarget')).toEqual([['sales']])

    const targetWrapper = mountHeader('target')
    runCommand(targetWrapper, 'Set as date column')
    expect(targetWrapper.emitted('setDate')).toEqual([['sales']])
  })

  it('offers known-future toggling for auxiliary columns', () => {
    expect(menuLabels(mountHeader('aux'))).toContain('Mark as known-future')
    expect(menuLabels(mountHeader('known_future'))).toContain('Unmark known-future')
    expect(menuLabels(mountHeader('aux'))).toContain('Remove auxiliary')
  })

  it('emits role events from menu commands', () => {
    const wrapper = mountHeader(null)
    runCommand(wrapper, 'Set as date column')
    runCommand(wrapper, 'Set as target')
    runCommand(wrapper, 'Set as auxiliary')
    expect(wrapper.emitted('setDate')).toEqual([['sales']])
    expect(wrapper.emitted('setTarget')).toEqual([['sales']])
    expect(wrapper.emitted('toggleAux')).toEqual([['sales']])

    const auxWrapper = mountHeader('aux')
    runCommand(auxWrapper, 'Mark as known-future')
    expect(auxWrapper.emitted('toggleKnownFuture')).toEqual([['sales']])
  })
})

describe('ForecastColumnHeader badges', () => {
  it.each([
    ['date', 'role-badge-date'],
    ['target', 'role-badge-target'],
    ['aux', 'role-badge-aux'],
    ['known_future', 'role-badge-known-future'],
  ] as const)('shows the %s badge', (role, testId) => {
    const wrapper = mountHeader(role)
    expect(wrapper.find(`[data-testid="${testId}"]`).exists()).toBe(true)
  })

  it('shows no badge for unassigned columns', () => {
    const wrapper = mountHeader(null)
    expect(wrapper.find('[data-testid^="role-badge-"]').exists()).toBe(false)
  })
})
