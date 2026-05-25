/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed } from 'vue';
const props = defineProps();
const valueText = computed(() => {
    if (typeof props.value === 'string')
        return props.value;
    if (typeof props.value === 'number')
        return props.value.toString();
    if (typeof props.value === 'boolean')
        return props.value.toString();
    if (typeof props.value === 'object')
        return JSON.stringify(props.value);
    return String(props.value ?? '');
});
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "cell" },
});
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { top: true, }, value: (__VLS_ctx.valueText) }, null, null);
/** @type {__VLS_StyleScopedClasses['cell']} */ ;
(__VLS_ctx.valueText);
// @ts-ignore
[vTooltip, valueText, valueText,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
