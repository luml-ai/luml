import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TagsList from './TagsList.vue'

describe('TagsList', () => {
  it('shows a single long tag instead of a +1 counter', () => {
    const wrapper = mount(TagsList, { props: { tags: ['production-experiment'] } })

    expect(wrapper.findAll('.tag')).toHaveLength(1)
    expect(wrapper.find('.tag').text()).toBe('production-experiment')
    expect(wrapper.find('.more-tags').exists()).toBe(false)
  })

  it('keeps the first long tag visible before the hidden tag count', () => {
    const wrapper = mount(TagsList, {
      props: { tags: ['production-experiment', 'staging', 'review'] },
    })

    expect(wrapper.findAll('.tag')).toHaveLength(1)
    expect(wrapper.find('.tag').text()).toBe('production-experiment')
    expect(wrapper.find('.more-tags').text()).toBe('+2')
  })

  it('shows short tags that fit and counts only the hidden ones', () => {
    const wrapper = mount(TagsList, { props: { tags: ['one', 'two', 'three', 'four'] } })

    expect(wrapper.findAll('.tag').map((tag) => tag.text())).toEqual(['one', 'two', 'three'])
    expect(wrapper.find('.more-tags').text()).toBe('+1')
  })

  it('shows a placeholder when there are no tags', () => {
    const wrapper = mount(TagsList, { props: { tags: [] } })

    expect(wrapper.text()).toBe('-')
  })
})
