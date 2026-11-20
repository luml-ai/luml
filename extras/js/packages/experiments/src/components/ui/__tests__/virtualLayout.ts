import { vi } from 'vitest'

/**
 * jsdom does no layout, so a VirtualScroller would compute NaN rows. Gives every element
 * the same size and zero paddings; undo with `vi.restoreAllMocks()`.
 */
export function mockVirtualLayout(viewport: number) {
  for (const prop of ['offsetHeight', 'offsetWidth', 'clientHeight', 'clientWidth'] as const) {
    vi.spyOn(HTMLElement.prototype, prop, 'get').mockReturnValue(viewport)
  }
  vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockImplementation(function (
    this: HTMLElement,
  ) {
    return this.parentElement
  })
  const getComputedStyle = window.getComputedStyle.bind(window)
  vi.spyOn(window, 'getComputedStyle').mockImplementation((element) => {
    const style = getComputedStyle(element)
    return new Proxy(style, {
      get: (target, key) => {
        const value = Reflect.get(target, key)
        return typeof key === 'string' && key.startsWith('padding') && !value ? '0px' : value
      },
    })
  })
}
