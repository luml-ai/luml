/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import UiId from '@/components/ui/UiId.vue';
const props = defineProps();
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ style: (__VLS_ctx.columnBodyStyle + 'width: 180px') },
});
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.name) }, null, null);
(__VLS_ctx.name);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "id-row" },
});
/** @type {__VLS_StyleScopedClasses['id-row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "id-text" },
});
/** @type {__VLS_StyleScopedClasses['id-text']} */ ;
const __VLS_0 = UiId || UiId;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    id: (__VLS_ctx.id),
    ...{ class: "id-value" },
}));
const __VLS_2 = __VLS_1({
    id: (__VLS_ctx.id),
    ...{ class: "id-value" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['id-value']} */ ;
// @ts-ignore
[columnBodyStyle, vTooltip, name, name, id,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
