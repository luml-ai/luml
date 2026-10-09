import { shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it } from 'vitest'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import LineageNode from '../LineageNode.vue'

const HandleStub = defineComponent({
  name: 'Handle',
  props: {
    position: { type: String, required: true },
    type: { type: String, required: true },
    connectable: { type: Boolean, required: true },
  },
  template:
    '<span class="handle" :data-position="position" :data-type="type" :data-connectable="connectable" />',
})

const MenuStub = defineComponent({
  name: 'Menu',
  props: { model: { type: Array, required: true } },
  template: '<div />',
})

function mountNode(
  variant: 'default' | 'main' | 'disabled',
  isDeleted = false,
  actionsDisabled = false,
) {
  return shallowMount(LineageNode, {
    props: {
      artifactType: ArtifactTypeEnum.model,
      title: isDeleted ? 'Old model' : 'Model',
      collectionName: 'Models',
      variant,
      isDeleted,
      deployments: [],
      tracks: [],
      actionsDisabled,
    },
    global: {
      stubs: {
        Handle: HandleStub,
        Button: {
          props: ['ariaLabel'],
          template: '<button :aria-label="ariaLabel"><slot name="icon" /></button>',
        },
        Menu: MenuStub,
      },
    },
  })
}

describe('LineageNode', () => {
  it('aligns the target handle left and source handle right', () => {
    const wrapper = mountNode('default')
    const handles = wrapper.findAll('.handle')

    expect(handles.map((handle) => handle.attributes())).toEqual([
      expect.objectContaining({
        'data-position': 'left',
        'data-type': 'target',
        'data-connectable': 'true',
      }),
      expect.objectContaining({
        'data-position': 'right',
        'data-type': 'source',
        'data-connectable': 'true',
      }),
    ])
    expect(wrapper.find('[aria-label="Artifact actions"]').exists()).toBe(true)
    expect(wrapper.attributes('data-lineage-state')).toBe('live')
  })

  it('highlights the focal node without showing its menu', () => {
    const wrapper = mountNode('main')

    expect(wrapper.attributes('data-lineage-state')).toBe('focal')
    expect(wrapper.find('[aria-label="Artifact actions"]').exists()).toBe(false)
  })

  it('disables replace and unlink while the graph cannot be rewired', () => {
    const items = (
      mountNode('default', false, true).findComponent(MenuStub).props('model') as {
        label: string
        disabled?: boolean
      }[]
    ).map((item) => [item.label, item.disabled])

    expect(items).toEqual([
      ['Replace', true],
      ['Unlink', true],
    ])
  })

  it('shows deleted state and menu while disabling both handles', () => {
    const wrapper = mountNode('disabled', true)

    expect(wrapper.text()).toContain('Deleted')
    expect(wrapper.attributes('data-lineage-state')).toBe('deleted')
    expect(wrapper.find('[aria-label="Artifact actions"]').exists()).toBe(true)
    expect(
      (wrapper.findComponent(MenuStub).props('model') as { label: string }[]).map(
        (item) => item.label,
      ),
    ).toEqual(['Replace', 'Unlink'])
    expect(
      wrapper.findAll('.handle').map((handle) => handle.attributes('data-connectable')),
    ).toEqual(['false', 'false'])
  })
})
