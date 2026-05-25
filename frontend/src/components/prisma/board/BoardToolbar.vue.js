/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Select } from 'primevue';
const __VLS_props = defineProps();
const emit = defineEmits();
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "board-toolbar" },
});
/** @type {__VLS_StyleScopedClasses['board-toolbar']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:modelValue': {} },
    modelValue: (__VLS_ctx.repositoryFilter),
    options: ([{ id: null, name: 'All repositories' }, ...__VLS_ctx.repositories]),
    optionLabel: "name",
    optionValue: "id",
    placeholder: "All repositories",
    size: "small",
    ...{ class: "repo-filter" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:modelValue': {} },
    modelValue: (__VLS_ctx.repositoryFilter),
    options: ([{ id: null, name: 'All repositories' }, ...__VLS_ctx.repositories]),
    optionLabel: "name",
    optionValue: "id",
    placeholder: "All repositories",
    size: "small",
    ...{ class: "repo-filter" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ 'update:modelValue': {} },
    { 'onUpdate:modelValue': (...[$event]) => {
            __VLS_ctx.emit('update:repositoryFilter', $event);
            // @ts-ignore
            [repositoryFilter, repositories, emit,];
        } });
/** @type {__VLS_StyleScopedClasses['repo-filter']} */ ;
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
