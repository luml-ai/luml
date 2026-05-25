/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ProviderStatus } from '@/lib/promt-fusion/prompt-fusion.interfaces';
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService';
const __VLS_props = defineProps();
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['item']} */ ;
/** @type {__VLS_StyleScopedClasses['item']} */ ;
/** @type {__VLS_StyleScopedClasses['status']} */ ;
/** @type {__VLS_StyleScopedClasses['status']} */ ;
/** @type {__VLS_StyleScopedClasses['status']} */ ;
/** @type {__VLS_StyleScopedClasses['connected']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "item" },
    ...{ class: ({ disabled: __VLS_ctx.provider.disabled }) },
});
/** @type {__VLS_StyleScopedClasses['item']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "left" },
});
/** @type {__VLS_StyleScopedClasses['left']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.img)({
    ...{ class: "image" },
    src: (__VLS_ctx.provider.image),
    alt: (__VLS_ctx.provider.name),
});
/** @type {__VLS_StyleScopedClasses['image']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "title" },
});
/** @type {__VLS_StyleScopedClasses['title']} */ ;
(__VLS_ctx.provider.name);
if (__VLS_ctx.provider.disabled) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "disabled-label" },
    });
    /** @type {__VLS_StyleScopedClasses['disabled-label']} */ ;
}
if (!__VLS_ctx.provider.disabled) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "right" },
    });
    /** @type {__VLS_StyleScopedClasses['right']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "status" },
        ...{ class: ({ connected: __VLS_ctx.provider.status === __VLS_ctx.ProviderStatus.connected }) },
    });
    /** @type {__VLS_StyleScopedClasses['status']} */ ;
    /** @type {__VLS_StyleScopedClasses['connected']} */ ;
    (__VLS_ctx.provider.status);
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onClick': {} },
        severity: "secondary",
        variant: "text",
        rounded: true,
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onClick': {} },
        severity: "secondary",
        variant: "text",
        rounded: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(!__VLS_ctx.provider.disabled))
                    return;
                __VLS_ctx.promptFusionService.openProviderSettings(__VLS_ctx.provider.id);
                // @ts-ignore
                [provider, provider, provider, provider, provider, provider, provider, provider, provider, ProviderStatus, promptFusionService,];
            } });
    const { default: __VLS_7 } = __VLS_3.slots;
    {
        const { icon: __VLS_8 } = __VLS_3.slots;
        let __VLS_9;
        /** @ts-ignore @type { | typeof __VLS_components.bolt | typeof __VLS_components.Bolt} */
        bolt;
        // @ts-ignore
        const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
            size: (14),
            color: "var(--p-button-text-secondary-color)",
        }));
        const __VLS_11 = __VLS_10({
            size: (14),
            color: "var(--p-button-text-secondary-color)",
        }, ...__VLS_functionalComponentArgsRest(__VLS_10));
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_3;
    var __VLS_4;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
