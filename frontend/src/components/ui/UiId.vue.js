/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { cutStringOnMiddle } from '@/helpers/helpers';
import { computed } from 'vue';
import UiCopyButton from './UiCopyButton.vue';
const props = withDefaults(defineProps(), {
    variant: 'text',
});
const formattedId = computed(() => cutStringOnMiddle(props.id, 8));
const __VLS_defaults = {
    variant: 'text',
};
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "id" },
    ...{ class: ({
            'id--button': __VLS_ctx.variant === 'button',
        }) },
});
/** @type {__VLS_StyleScopedClasses['id']} */ ;
/** @type {__VLS_StyleScopedClasses['id--button']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
(__VLS_ctx.formattedId);
const __VLS_0 = UiCopyButton || UiCopyButton;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    text: (__VLS_ctx.id),
}));
const __VLS_2 = __VLS_1({
    text: (__VLS_ctx.id),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
// @ts-ignore
[variant, formattedId, id,];
const __VLS_export = (await import('vue')).defineComponent({
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};
