import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { Form } from '@primevue/forms'
import Button from 'primevue/button'
import FloatLabel from 'primevue/floatlabel'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Password from 'primevue/password'
import UserChangeEmail from './UserChangeEmail.vue'

const { changeEmail } = vi.hoisted(() => ({ changeEmail: vi.fn() }))
vi.mock('@/lib/api', () => ({ api: { changeEmail } }))

function mountDialog() {
  return mount(UserChangeEmail, {
    global: {
      plugins: [PrimeVue],
      components: {
        DForm: Form,
        DButton: Button,
        DFloatLabel: FloatLabel,
        DInputText: InputText,
        DMessage: Message,
        DPassword: Password,
      },
    },
  })
}

describe('change email dialog', () => {
  let wrapper: ReturnType<typeof mountDialog>
  beforeEach(() => {
    changeEmail.mockReset().mockResolvedValue({
      detail: 'If this address can be used, we have sent a confirmation link to it',
    })
    wrapper = mountDialog()
  })
  afterEach(() => wrapper.unmount())

  async function submit(email = 'new@example.com', password = 'current-password') {
    await wrapper.get('input[name="new_email"]').setValue(email)
    await wrapper.get('input[name="current_password"]').setValue(password)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
  }

  it('sends the new address and current password and shows the uniform response', async () => {
    await submit()
    expect(changeEmail).toHaveBeenCalledExactlyOnceWith({
      new_email: 'new@example.com',
      current_password: 'current-password',
    })
    expect(wrapper.text()).toContain(
      'If this address can be used, we have sent a confirmation link to it',
    )
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it.each([
    ['bad', 'current-password'],
    ['new@example.com', 'short'],
    ['', ''],
  ])('rejects invalid inputs %s', async (email, password) => {
    await submit(email, password)
    expect(changeEmail).not.toHaveBeenCalled()
    expect(wrapper.findAll('.p-message-error').length).toBeGreaterThan(0)
  })

  it.each(['Invalid current password', 'New email must differ from the current address'])(
    'shows backend error %s',
    async (message) => {
      changeEmail.mockRejectedValueOnce({ response: { data: { detail: message } } })
      await submit()
      expect(wrapper.text()).toContain(message)
      expect(wrapper.find('form').exists()).toBe(true)
    },
  )

  it('prevents duplicate requests while sending', async () => {
    let resolve!: (value: { detail: string }) => void
    changeEmail.mockReturnValueOnce(
      new Promise((done) => {
        resolve = done
      }),
    )
    await submit()
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(changeEmail).toHaveBeenCalledTimes(1)
    resolve({ detail: 'Link sent' })
    await flushPromises()
  })

  it('names both inputs through their labels', () => {
    for (const id of ['new-email', 'current-password']) {
      const input = wrapper.get(`input#${id}`)
      expect(wrapper.get(`label[for="${id}"]`).text()).not.toBe('')
      expect(input.element.tagName).toBe('INPUT')
    }
    expect(wrapper.get('input#current-password').attributes('autocomplete')).toBe(
      'current-password',
    )
  })
})
