/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { onMounted, onBeforeUnmount, ref } from 'vue';
import NotebooksList from './NotebooksList.vue';
import NotebookCreator from './NotebookCreator.vue';
import { useNotebooksStore } from '@/stores/notebooks';
import { useToast } from 'primevue';
const notebooksStore = useNotebooksStore();
const toast = useToast();
const loading = ref(false);
const fetchNotebooks = async () => {
    try {
        loading.value = true;
        await notebooksStore.getNotebooks();
    }
    catch {
        toast.add({
            severity: 'error',
            summary: 'Error',
            detail: 'Failed to receive notebooks',
            life: 2000,
        });
    }
    finally {
        loading.value = false;
    }
};
const handleVisibilityChange = () => {
    if (!document.hidden) {
        fetchNotebooks();
    }
};
const handleWindowFocus = () => {
    fetchNotebooks();
};
onMounted(async () => {
    await fetchNotebooks();
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleWindowFocus);
});
onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    window.removeEventListener('focus', handleWindowFocus);
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "notebooks" },
});
/** @type {__VLS_StyleScopedClasses['notebooks']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "top" },
});
/** @type {__VLS_StyleScopedClasses['top']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "headings" },
});
/** @type {__VLS_StyleScopedClasses['headings']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "main-title" },
});
/** @type {__VLS_StyleScopedClasses['main-title']} */ ;
const __VLS_0 = NotebookCreator || NotebookCreator;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "notebook-content" },
});
/** @type {__VLS_StyleScopedClasses['notebook-content']} */ ;
const __VLS_5 = NotebooksList || NotebooksList;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({}));
const __VLS_7 = __VLS_6({}, ...__VLS_functionalComponentArgsRest(__VLS_6));
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
