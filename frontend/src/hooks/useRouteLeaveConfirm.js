import { useConfirm } from 'primevue/useconfirm';
import { onBeforeMount, onBeforeUnmount, ref } from 'vue';
import { useRouter } from 'vue-router';
export const useRouteLeaveConfirm = (confirmationOptions) => {
    const router = useRouter();
    const confirm = useConfirm();
    const guard = ref(true);
    function setGuard(value) {
        guard.value = value;
    }
    function accept(next) {
        next();
    }
    const confirmExit = (next) => {
        confirm.require({ ...confirmationOptions, accept: () => accept(next) });
    };
    const removeGuard = router.beforeEach((to, from, next) => {
        if (!guard.value)
            return next();
        confirmExit(next);
    });
    function onBeforeUnload(event) {
        if (!guard.value)
            return;
        event.preventDefault();
    }
    onBeforeMount(() => {
        window.addEventListener('beforeunload', onBeforeUnload);
    });
    onBeforeUnmount(() => {
        removeGuard();
        window.removeEventListener('beforeunload', onBeforeUnload);
    });
    return { setGuard };
};
