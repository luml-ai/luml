/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { MultiSelect } from 'primevue';
import { ref, watch } from 'vue';
const multiSelectPt = {
    pcHeaderCheckbox: {
        root: {
            style: 'display: none !important;',
        },
    },
    pcFilter: {
        root: {
            class: 'p-inputtext-sm p-inputfield-sm',
        },
    },
};
const props = defineProps();
const modelValue = defineModel('modelValue');
const state = ref(null);
function onBeforeHide() {
    modelValue.value = state.value ? [...state.value] : null;
}
watch(modelValue, (value) => {
    state.value = value ? [...value] : null;
});
let __VLS_modelEmit;
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
    ...{ class: "wrapper" },
});
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.MultiSelect} */
MultiSelect;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onBeforeHide': {} },
    id: "metrics",
    modelValue: (__VLS_ctx.state),
    options: (props.metrics),
    placeholder: "Select metrics",
    fluid: true,
    ...{ class: "select" },
    size: "small",
    filter: true,
    selectionLimit: (100),
    virtualScrollerOptions: ({ itemSize: 35 }),
    pt: (__VLS_ctx.multiSelectPt),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onBeforeHide': {} },
    id: "metrics",
    modelValue: (__VLS_ctx.state),
    options: (props.metrics),
    placeholder: "Select metrics",
    fluid: true,
    ...{ class: "select" },
    size: "small",
    filter: true,
    selectionLimit: (100),
    virtualScrollerOptions: ({ itemSize: 35 }),
    pt: (__VLS_ctx.multiSelectPt),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ beforeHide: {} },
    { onBeforeHide: (__VLS_ctx.onBeforeHide) });
/** @type {__VLS_StyleScopedClasses['select']} */ ;
var __VLS_3;
var __VLS_4;
// @ts-ignore
[state, multiSelectPt, onBeforeHide,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
