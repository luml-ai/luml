import { config } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Tooltip from 'primevue/tooltip'

/** jsdom has no ResizeObserver; Vue Flow observes its viewport. */
if (!('ResizeObserver' in globalThis)) {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  } as unknown as typeof ResizeObserver
}

/** jsdom implements no media queries; PrimeVue's Select binds an orientation listener. */
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
}

/** jsdom has no IntersectionObserver; CodeMirror watches its own visibility. */
if (!('IntersectionObserver' in globalThis)) {
  globalThis.IntersectionObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
    takeRecords(): [] {
      return []
    }
  } as unknown as typeof IntersectionObserver
}

/**
 * jsdom lays nothing out, so every measurement CodeMirror takes is a zero. The
 * missing pieces are stubbed rather than the editor mocked away: a real
 * `EditorView` over a real document is what the specs are for, and only the
 * geometry is unavailable here.
 */
const NO_BOX: DOMRect = {
  x: 0,
  y: 0,
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  width: 0,
  height: 0,
  toJSON: () => ({}),
}

if (typeof Range !== 'undefined') {
  Range.prototype.getBoundingClientRect = () => NO_BOX
  Range.prototype.getClientRects = () =>
    Object.assign([] as DOMRect[], { item: () => null }) as unknown as DOMRectList
}

if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

config.global.plugins = [PrimeVue]
config.global.directives = { tooltip: Tooltip }
