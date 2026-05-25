/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService';
const __VLS_props = defineProps();
const __VLS_emit = defineEmits();
function onLinkClick(option) {
    AnalyticsService.track(AnalyticsTrackKeysEnum.select_prompt_optimization, { option });
}
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
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog'] | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog']} */
dDialog;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.modelValue),
    modal: true,
    ...{ style: {} },
    dismissableMask: true,
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.modelValue),
    modal: true,
    ...{ style: {} },
    dismissableMask: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ 'update:visible': {} },
    { 'onUpdate:visible': ((value) => __VLS_ctx.$emit('update:modelValue', value)) });
var __VLS_7;
const { default: __VLS_8 } = __VLS_3.slots;
{
    const { header: __VLS_9 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "dialog-title" },
    });
    /** @type {__VLS_StyleScopedClasses['dialog-title']} */ ;
    // @ts-ignore
    [modelValue, $emit,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "dialog-sub-title" },
});
/** @type {__VLS_StyleScopedClasses['dialog-sub-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
    ...{ class: "prompt-menu" },
});
/** @type {__VLS_StyleScopedClasses['prompt-menu']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
    ...{ class: "prompt-menu-item" },
});
/** @type {__VLS_StyleScopedClasses['prompt-menu-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "prompt-menu-item-title" },
});
/** @type {__VLS_StyleScopedClasses['prompt-menu-item-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "prompt-menu-item-description" },
});
/** @type {__VLS_StyleScopedClasses['prompt-menu-item-description']} */ ;
let __VLS_10;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
    asChild: true,
    severity: "secondary",
}));
const __VLS_12 = __VLS_11({
    asChild: true,
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_11));
{
    const { default: __VLS_15 } = __VLS_13.slots;
    const [slotProps] = __VLS_vSlot(__VLS_15);
    let __VLS_16;
    /** @ts-ignore @type { | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link'] | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link']} */
    routerLink;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({
        ...{ 'onClick': {} },
        to: ({ name: 'prompt-fusion' }),
        ...{ class: "prompt-menu-item-button" },
        ...{ class: (slotProps.class) },
    }));
    const __VLS_18 = __VLS_17({
        ...{ 'onClick': {} },
        to: ({ name: 'prompt-fusion' }),
        ...{ class: "prompt-menu-item-button" },
        ...{ class: (slotProps.class) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    let __VLS_21;
    const __VLS_22 = ({ click: {} },
        { onClick: (() => __VLS_ctx.onLinkClick('free_form')) });
    /** @type {__VLS_StyleScopedClasses['prompt-menu-item-button']} */ ;
    const { default: __VLS_23 } = __VLS_19.slots;
    // @ts-ignore
    [onLinkClick,];
    var __VLS_19;
    var __VLS_20;
    // @ts-ignore
    [];
    __VLS_13.slots['' /* empty slot name completion */];
}
var __VLS_13;
__VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
    ...{ class: "prompt-menu-item" },
});
/** @type {__VLS_StyleScopedClasses['prompt-menu-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "prompt-menu-item-title" },
});
/** @type {__VLS_StyleScopedClasses['prompt-menu-item-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "prompt-menu-item-description" },
});
/** @type {__VLS_StyleScopedClasses['prompt-menu-item-description']} */ ;
let __VLS_24;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
    asChild: true,
    severity: "secondary",
}));
const __VLS_26 = __VLS_25({
    asChild: true,
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
{
    const { default: __VLS_29 } = __VLS_27.slots;
    const [slotProps] = __VLS_vSlot(__VLS_29);
    let __VLS_30;
    /** @ts-ignore @type { | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link'] | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link']} */
    routerLink;
    // @ts-ignore
    const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
        ...{ 'onClick': {} },
        to: ({ name: 'prompt-fusion', params: { mode: 'data-driven' } }),
        ...{ class: "prompt-menu-item-button" },
        ...{ class: (slotProps.class) },
    }));
    const __VLS_32 = __VLS_31({
        ...{ 'onClick': {} },
        to: ({ name: 'prompt-fusion', params: { mode: 'data-driven' } }),
        ...{ class: "prompt-menu-item-button" },
        ...{ class: (slotProps.class) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_31));
    let __VLS_35;
    const __VLS_36 = ({ click: {} },
        { onClick: (() => __VLS_ctx.onLinkClick('data_driven')) });
    /** @type {__VLS_StyleScopedClasses['prompt-menu-item-button']} */ ;
    const { default: __VLS_37 } = __VLS_33.slots;
    // @ts-ignore
    [onLinkClick,];
    var __VLS_33;
    var __VLS_34;
    // @ts-ignore
    [];
    __VLS_27.slots['' /* empty slot name completion */];
}
var __VLS_27;
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
