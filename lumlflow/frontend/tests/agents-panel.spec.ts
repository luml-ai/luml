import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import type { AgentHarness } from '@/flow/api/types'
import AgentsPanel from '@/components/notebooks/AgentsPanel.vue'

const CLAUDE_HARNESS: AgentHarness = {
  id: 'claude-code',
  display_name: 'Claude Code',
  state: 'not set up',
  config_path: '/home/dana/.claude.json',
  snippet: '{"mcpServers":{"lumlflow":{"command":"lumlflow","args":["mcp"]}}}',
  can_setup: true,
  action: 'setup',
  consent_required: true,
  consent_prompt: 'Allow lumlflow to update /home/dana/.claude.json and keep its entry current?',
  post_write_hint: 'approve the server when Claude Code asks',
  shell: true,
  shell_hint: 'also works without setup: run `lumlflow guide` in it',
  error: null,
}

function agentHarness(overrides: Partial<AgentHarness>): AgentHarness {
  return { ...CLAUDE_HARNESS, ...overrides }
}

beforeEach(() => {
  document.body.innerHTML = ''
})

describe('the Agents panel', () => {
  function panelButton(wrapper: ReturnType<typeof mount>, label: string) {
    const found = wrapper.findAll('button').find((candidate) => candidate.text() === label)
    expect(found, `no button labelled "${label}"`).toBeTruthy()
    return found!
  }

  function overlayButton(label: string): HTMLButtonElement {
    const found = [...document.body.querySelectorAll<HTMLButtonElement>('button')].find(
      (candidate) => candidate.textContent?.trim() === label,
    )
    expect(found, `no overlay button labelled "${label}"`).toBeTruthy()
    return found!
  }

  it('selects harnesses, names the config in consent, and waits for approval', async () => {
    const wrapper = mount(AgentsPanel, { props: { harnesses: [CLAUDE_HARNESS] } })

    expect(wrapper.text()).toContain('Claude Code')
    expect(wrapper.text()).toContain('not set up')
    expect(wrapper.text()).toContain('lumlflow guide')

    await wrapper.get('input[type="checkbox"]').setValue(true)
    await panelButton(wrapper, 'Set up').trigger('click')
    await nextTick()

    expect(document.body.textContent).toContain('/home/dana/.claude.json')
    overlayButton('Not now').click()
    await nextTick()
    expect(wrapper.emitted('setup')).toBeUndefined()

    await panelButton(wrapper, 'Set up').trigger('click')
    await nextTick()
    overlayButton('Allow and set up').click()
    await nextTick()

    expect(wrapper.emitted('setup')).toEqual([[['claude-code'], true]])
    wrapper.unmount()
  })

  it('offers state-specific actions and manual repair details', async () => {
    const wrapper = mount(AgentsPanel, {
      props: {
        harnesses: [
          agentHarness({
            id: 'cursor',
            display_name: 'Cursor',
            state: 'out of date',
            action: 'update',
            consent_required: false,
            consent_prompt: null,
            error: 'the config does not parse',
          }),
          agentHarness({
            id: 'jetbrains-ai',
            display_name: 'JetBrains AI',
            can_setup: false,
            action: null,
            config_path: 'Settings > Tools > AI Assistant > MCP',
            shell: false,
            shell_hint: null,
          }),
          agentHarness({
            state: 'set up',
            action: null,
            consent_required: false,
            consent_prompt: null,
          }),
        ],
      },
    })

    expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('the config does not parse')
    expect(wrapper.text()).toContain('Settings > Tools > AI Assistant > MCP')
    expect(wrapper.text()).toContain('mcpServers')
    expect(
      wrapper.findAll('button').filter((candidate) => candidate.text() === 'Set up'),
    ).toHaveLength(0)

    await panelButton(wrapper, 'Update').trigger('click')
    await panelButton(wrapper, 'Remove').trigger('click')

    expect(wrapper.emitted('update')).toEqual([['cursor']])
    expect(wrapper.emitted('remove')).toEqual([['claude-code']])
    wrapper.unmount()
  })
})
