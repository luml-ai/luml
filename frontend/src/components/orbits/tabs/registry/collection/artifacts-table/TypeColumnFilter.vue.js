/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ARTIFACT_TYPE_OPTIONS } from './models-table.data';
import { Checkbox } from 'primevue';
const modelValue = defineModel('modelValue', { default: [] });
const __VLS_defaultModels = {
    'modelValue': [],
};
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
for (const [type] of __VLS_vFor((__VLS_ctx.ARTIFACT_TYPE_OPTIONS))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (type.value),
        ...{ class: "filter-checkbox" },
    });
    /** @type {__VLS_StyleScopedClasses['filter-checkbox']} */ ;
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.Checkbox} */
    Checkbox;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        modelValue: (__VLS_ctx.modelValue),
        name: "type",
        inputId: (type.value),
        value: (type.value),
    }));
    const __VLS_2 = __VLS_1({
        modelValue: (__VLS_ctx.modelValue),
        name: "type",
        inputId: (type.value),
        value: (type.value),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: (type.value),
    });
    (type.label);
    const __VLS_5 = (type.icon);
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        size: (12),
        color: (type.color),
    }));
    const __VLS_7 = __VLS_6({
        size: (12),
        color: (type.color),
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    // @ts-ignore
    [ARTIFACT_TYPE_OPTIONS, modelValue,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
