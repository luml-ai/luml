/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import TasksListItem from './TasksListItem.vue';
const __VLS_props = defineProps();
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['items']} */ ;
/** @type {__VLS_StyleScopedClasses['items']} */ ;
/** @type {__VLS_StyleScopedClasses['items']} */ ;
/** @type {__VLS_StyleScopedClasses['items']} */ ;
/** @type {__VLS_StyleScopedClasses['sub-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "wrapper" },
});
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "sub-title" },
});
/** @type {__VLS_StyleScopedClasses['sub-title']} */ ;
(__VLS_ctx.label);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "items" },
});
/** @type {__VLS_StyleScopedClasses['items']} */ ;
for (const [task] of __VLS_vFor((__VLS_ctx.tasks))) {
    const __VLS_0 = TasksListItem;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        task: (task),
        key: (task.id),
    }));
    const __VLS_2 = __VLS_1({
        task: (task),
        key: (task.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    // @ts-ignore
    [label, tasks,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
