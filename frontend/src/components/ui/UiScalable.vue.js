/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Dialog } from 'primevue';
import { Minimize2 } from 'lucide-vue-next';
const __VLS_props = defineProps();
const scaled = defineModel('modelValue');
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
var __VLS_0 = {};
let __VLS_2;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_3 = __VLS_asFunctionalComponent1(__VLS_2, new __VLS_2({
    visible: (__VLS_ctx.scaled),
    header: (__VLS_ctx.title.toUpperCase()),
    blockScroll: true,
    ...{ class: "p-dialog-maximized" },
}));
const __VLS_4 = __VLS_3({
    visible: (__VLS_ctx.scaled),
    header: (__VLS_ctx.title.toUpperCase()),
    blockScroll: true,
    ...{ class: "p-dialog-maximized" },
}, ...__VLS_functionalComponentArgsRest(__VLS_3));
/** @type {__VLS_StyleScopedClasses['p-dialog-maximized']} */ ;
const { default: __VLS_7 } = __VLS_5.slots;
{
    const { closeicon: __VLS_8 } = __VLS_5.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.Minimize2} */
    Minimize2;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        size: (14),
    }));
    const __VLS_11 = __VLS_10({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    // @ts-ignore
    [scaled, title,];
}
var __VLS_14 = {};
// @ts-ignore
[];
var __VLS_5;
// @ts-ignore
var __VLS_1 = __VLS_0, __VLS_15 = __VLS_14;
// @ts-ignore
[];
const __VLS_base = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
const __VLS_export = {};
export default {};
