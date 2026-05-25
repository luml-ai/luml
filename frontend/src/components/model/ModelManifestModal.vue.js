/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Dialog } from 'primevue';
import { FileJson2 } from 'lucide-vue-next';
import { ContentTypeEnum } from '../ui/multi-type-text/interfaces';
import UiMultiTypeText from '../ui/multi-type-text/UiMultiTypeText.vue';
const __VLS_props = defineProps();
const visible = defineModel('visible');
const dialogPT = {
    footer: {
        style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
    },
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
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    visible: (__VLS_ctx.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
{
    const { header: __VLS_7 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "dialog-title" },
    });
    /** @type {__VLS_StyleScopedClasses['dialog-title']} */ ;
    let __VLS_8;
    /** @ts-ignore @type { | typeof __VLS_components.FileJson2} */
    FileJson2;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        size: (20),
        color: "var(--p-primary-color)",
    }));
    const __VLS_10 = __VLS_9({
        size: (20),
        color: "var(--p-primary-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [visible, dialogPT,];
}
const __VLS_13 = UiMultiTypeText || UiMultiTypeText;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    title: (''),
    text: (__VLS_ctx.manifest),
    initialType: (__VLS_ctx.ContentTypeEnum.yaml),
}));
const __VLS_15 = __VLS_14({
    title: (''),
    text: (__VLS_ctx.manifest),
    initialType: (__VLS_ctx.ContentTypeEnum.yaml),
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
// @ts-ignore
[manifest, ContentTypeEnum,];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
