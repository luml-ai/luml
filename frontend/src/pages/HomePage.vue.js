/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { onMounted } from 'vue';
import TasksList from '@/components/homepage-tasks/TasksList.vue';
import { useUserStore } from '@/stores/user';
import { useToast } from 'primevue/usetoast';
import { passwordResetSuccessToast } from '@/lib/primevue/data/toasts';
import { availableTasks } from '@/constants/constants';
const userStore = useUserStore();
const toast = useToast();
const showPasswordMessage = () => {
    toast.add(passwordResetSuccessToast);
};
onMounted(() => {
    userStore.isPasswordHasBeenChanged && showPasswordMessage();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['body']} */ ;
/** @type {__VLS_StyleScopedClasses['headings']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content" },
});
/** @type {__VLS_StyleScopedClasses['content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "headings" },
});
/** @type {__VLS_StyleScopedClasses['headings']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "main-title" },
});
/** @type {__VLS_StyleScopedClasses['main-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "sub-title" },
});
/** @type {__VLS_StyleScopedClasses['sub-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "body" },
});
/** @type {__VLS_StyleScopedClasses['body']} */ ;
const __VLS_0 = TasksList;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    label: "Available tasks",
    tasks: (__VLS_ctx.availableTasks),
}));
const __VLS_2 = __VLS_1({
    label: "Available tasks",
    tasks: (__VLS_ctx.availableTasks),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
// @ts-ignore
[availableTasks,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
