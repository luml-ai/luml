import type { ConfirmationOptions } from 'primevue/confirmationoptions'
import { useConfirm } from 'primevue/useconfirm'
import { onMounted, onUnmounted, ref } from 'vue'
import { type NavigationGuardNext, useRouter } from 'vue-router'

export const useRouteLeaveConfirm = (confirmationOptions: ConfirmationOptions) => {
  const router = useRouter()
  const confirm = useConfirm()
  const guard = ref(true)

  function setGuard(value: boolean) {
    guard.value = value
  }

  function accept(next: NavigationGuardNext) {
    next()
  }

  const confirmExit = (next: NavigationGuardNext) => {
    confirm.require({ ...confirmationOptions, accept: () => accept(next) })
  }

  const removeGuard = router.beforeEach((to, from, next) => {
    if (!guard.value) return next()

    confirmExit(next)
  })

  function onBeforeUnload(event: BeforeUnloadEvent) {
    if (!guard.value) return
    event.preventDefault()
  }

  onMounted(() => {
    window.addEventListener('beforeunload', onBeforeUnload)
  })

  onUnmounted(() => {
    removeGuard()
    window.removeEventListener('beforeunload', onBeforeUnload)
  })

  return { setGuard }
}
