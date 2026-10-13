import { useEventListener } from '@vueuse/core'

const ZOOM_KEYS = ['+', '-', '=', '0']

export function useDisableBrowserZoom() {
  useEventListener(
    window,
    'wheel',
    (event: WheelEvent) => {
      if (event.ctrlKey || event.metaKey) event.preventDefault()
    },
    { passive: false },
  )

  useEventListener(window, 'keydown', (event: KeyboardEvent) => {
    if ((event.ctrlKey || event.metaKey) && ZOOM_KEYS.includes(event.key)) {
      event.preventDefault()
    }
  })

  const preventGesture = (event: Event) => event.preventDefault()
  useEventListener(window, 'gesturestart', preventGesture)
  useEventListener(window, 'gesturechange', preventGesture)
  useEventListener(window, 'gestureend', preventGesture)
}
