import { onScopeDispose, watch } from 'vue'

let locks = 0
let previousOverflow = ''

export function useBodyScrollLock(open: () => boolean): void {
  let locked = false

  function release(): void {
    if (!locked) return
    locked = false
    locks -= 1
    if (locks === 0) document.body.style.overflow = previousOverflow
  }

  watch(
    open,
    (open) => {
      if (!open) {
        release()
      } else if (!locked) {
        if (locks === 0) previousOverflow = document.body.style.overflow
        locks += 1
        locked = true
        document.body.style.overflow = 'hidden'
      }
    },
    { immediate: true },
  )

  onScopeDispose(release)
}
