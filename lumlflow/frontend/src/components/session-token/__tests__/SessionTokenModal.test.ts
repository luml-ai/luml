// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { api } from '@/api/client'
import { page, sessionTokenRejected } from '@/api/session'
import SessionTokenModal from '../SessionTokenModal.vue'

vi.mock('@/api/client', () => ({ api: { get: vi.fn() } }))

const stubs = {
  Dialog: {
    props: ['visible'],
    template: '<div v-if="visible"><slot /><slot name="footer" /></div>',
  },
  InputText: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  Button: { props: ['label'], template: '<button type="button">{{ label }}</button>' },
  Message: { template: '<p class="error"><slot /></p>' },
}

function unauthorized() {
  const config = { headers: {} } as InternalAxiosRequestConfig
  return new AxiosError('Unauthorized', '401', config, null, {
    data: {},
    status: 401,
    statusText: 'Unauthorized',
    headers: {},
    config,
  })
}

async function submit(launchUrl: string) {
  const wrapper = mount(SessionTokenModal, { global: { stubs } })
  await wrapper.find('input').setValue(launchUrl)
  await wrapper.find('button').trigger('click')
  await flushPromises()
  return wrapper
}

describe('SessionTokenModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    sessionTokenRejected.value = true
  })

  it('stays hidden while the session token is accepted', () => {
    sessionTokenRejected.value = false
    const wrapper = mount(SessionTokenModal, { global: { stubs } })
    expect(wrapper.find('input').exists()).toBe(false)
  })

  it('opens Flow with the token from a pasted launch URL', async () => {
    const reload = vi.spyOn(page, 'reload').mockImplementation(() => {})
    vi.mocked(api.get).mockResolvedValue({ data: {} })
    await submit('http://127.0.0.1:5065/#session-token=pasted-session')
    expect(localStorage.getItem('flow-session-token')).toBe('pasted-session')
    expect(api.get).toHaveBeenCalledWith('/groups', { params: { limit: 1 } })
    expect(reload).toHaveBeenCalledOnce()
  })

  it('asks for the whole launch URL when it has no token', async () => {
    const wrapper = await submit('http://127.0.0.1:5065/')
    expect(api.get).not.toHaveBeenCalled()
    expect(wrapper.find('.error').text()).toContain('#session-token=')
  })

  it('explains that Flow rejected the token', async () => {
    const reload = vi.spyOn(page, 'reload').mockImplementation(() => {})
    vi.mocked(api.get).mockRejectedValue(unauthorized())
    const wrapper = await submit('http://127.0.0.1:5065/#session-token=stale')
    expect(reload).not.toHaveBeenCalled()
    expect(wrapper.find('.error').text()).toContain('does not accept that token')
  })
})
