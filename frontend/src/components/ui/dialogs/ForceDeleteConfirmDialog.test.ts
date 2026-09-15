import { mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { describe, expect, it } from 'vitest'
import ForceDeleteConfirmDialog from './ForceDeleteConfirmDialog.vue'

const DialogStub = defineComponent({
  props: {
    visible: Boolean,
    header: String,
  },
  template:
    '<section v-if="visible"><h1>{{ header }}</h1><slot /><footer><slot name="footer" /></footer></section>',
})

const ButtonStub = defineComponent({
  props: {
    disabled: Boolean,
  },
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
})

const InputTextStub = defineComponent({
  inheritAttrs: false,
  props: {
    modelValue: String,
  },
  emits: ['update:modelValue'],
  template:
    '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
})

function mountDialog(secondaryActionLabel?: string) {
  return mount(ForceDeleteConfirmDialog, {
    props: {
      visible: true,
      title: 'Force delete?',
      text: 'Type delete.',
      loading: false,
      secondaryActionLabel,
    },
    global: {
      stubs: {
        Dialog: DialogStub,
        Button: ButtonStub,
        InputText: InputTextStub,
      },
    },
  })
}

describe('ForceDeleteConfirmDialog', () => {
  it('renders an optional ungated secondary action while keeping force gated', async () => {
    const withoutSecondaryAction = mountDialog()
    expect(withoutSecondaryAction.text()).not.toContain('Try again')

    const wrapper = mountDialog('Try again')
    const buttons = wrapper.findAll('button')
    const secondaryButton = buttons.find((button) => button.text() === 'Try again')
    const forceButton = buttons.find((button) => button.text() === 'force delete')

    expect(secondaryButton?.attributes('disabled')).toBeUndefined()
    expect(forceButton?.attributes('disabled')).toBeDefined()

    await secondaryButton?.trigger('click')
    expect(wrapper.emitted('secondaryAction')).toHaveLength(1)

    await wrapper.get('input').setValue('delete')
    await nextTick()
    expect(forceButton?.attributes('disabled')).toBeUndefined()

    await forceButton?.trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })
})
