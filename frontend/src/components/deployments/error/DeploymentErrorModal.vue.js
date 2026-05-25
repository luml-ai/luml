/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { deploymentErrorDialogPt } from '../deployments.const';
import { Button, Dialog } from 'primevue';
import { Copy, CopyCheck } from 'lucide-vue-next';
import { computed, ref } from 'vue';
const props = defineProps();
const visible = defineModel('visible');
const formattedError = computed(() => {
    return props.error
        .replace(/\\n/g, '\n')
        .replace(/\\t/g, '\t')
        .trim()
        .replace(/^\{/, '')
        .replace(/\}$/, '');
});
const copied = ref(false);
function copy() {
    copied.value = true;
    navigator.clipboard.writeText(formattedError.value);
    setTimeout(() => {
        copied.value = false;
    }, 2000);
}
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
    pt: (__VLS_ctx.deploymentErrorDialogPt),
    modal: true,
    draggable: (false),
    dismissableMask: true,
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    pt: (__VLS_ctx.deploymentErrorDialogPt),
    modal: true,
    draggable: (false),
    dismissableMask: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
{
    const { header: __VLS_7 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({});
    (__VLS_ctx.reason);
    // @ts-ignore
    [visible, deploymentErrorDialogPt, reason,];
}
{
    const { default: __VLS_8 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.pre, __VLS_intrinsics.pre)({
        ...{ class: "error-body" },
    });
    /** @type {__VLS_StyleScopedClasses['error-body']} */ ;
    (__VLS_ctx.formattedError);
    // @ts-ignore
    [formattedError,];
}
{
    const { footer: __VLS_9 } = __VLS_3.slots;
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        ...{ 'onClick': {} },
        label: "copy",
    }));
    const __VLS_12 = __VLS_11({
        ...{ 'onClick': {} },
        label: "copy",
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    let __VLS_15;
    const __VLS_16 = ({ click: {} },
        { onClick: (__VLS_ctx.copy) });
    const { default: __VLS_17 } = __VLS_13.slots;
    {
        const { icon: __VLS_18 } = __VLS_13.slots;
        const __VLS_19 = (__VLS_ctx.copied ? __VLS_ctx.CopyCheck : __VLS_ctx.Copy);
        // @ts-ignore
        const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
            size: (12),
        }));
        const __VLS_21 = __VLS_20({
            size: (12),
        }, ...__VLS_functionalComponentArgsRest(__VLS_20));
        // @ts-ignore
        [copy, copied, CopyCheck, Copy,];
    }
    // @ts-ignore
    [];
    var __VLS_13;
    var __VLS_14;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
