/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { Checkbox, Button, Dialog, useToast } from 'primevue';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { useDeploymentsStore } from '@/stores/deployments';
import { getErrorMessage } from '@/helpers/helpers';
const props = defineProps();
const emits = defineEmits();
const toast = useToast();
const deploymentsStore = useDeploymentsStore();
const visible = defineModel('visible');
const accept = ref(false);
const loading = ref(false);
async function deleteDeployment() {
    try {
        loading.value = true;
        await deploymentsStore.deleteDeployment(props.organizationId, props.orbitId, props.deploymentId);
        toast.add(simpleSuccessToast(`Deployment "${props.name}" is shutting down.`));
        emits('delete');
    }
    catch (e) {
        toast.add(simpleErrorToast(getErrorMessage(e, 'Could not delete deployment')));
    }
    finally {
        loading.value = false;
    }
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
    modal: true,
    draggable: (false),
    header: "Stop this deployment?",
    ...{ style: ({ width: '350px' }) },
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    modal: true,
    draggable: (false),
    header: "Stop this deployment?",
    ...{ style: ({ width: '350px' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text" },
});
/** @type {__VLS_StyleScopedClasses['text']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "checkbox-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['checkbox-wrapper']} */ ;
let __VLS_7;
/** @ts-ignore @type { | typeof __VLS_components.Checkbox} */
Checkbox;
// @ts-ignore
const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
    modelValue: (__VLS_ctx.accept),
    inputId: "deleteAccept",
    binary: true,
}));
const __VLS_9 = __VLS_8({
    modelValue: (__VLS_ctx.accept),
    inputId: "deleteAccept",
    binary: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "deleteAccept",
});
{
    const { footer: __VLS_12 } = __VLS_3.slots;
    let __VLS_13;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.loading),
    }));
    const __VLS_15 = __VLS_14({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_14));
    let __VLS_18;
    const __VLS_19 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.visible = false;
                // @ts-ignore
                [visible, visible, accept, loading,];
            } });
    const { default: __VLS_20 } = __VLS_16.slots;
    // @ts-ignore
    [];
    var __VLS_16;
    var __VLS_17;
    let __VLS_21;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
        ...{ 'onClick': {} },
        severity: "warn",
        outlined: true,
        disabled: (!__VLS_ctx.accept),
        loading: (__VLS_ctx.loading),
    }));
    const __VLS_23 = __VLS_22({
        ...{ 'onClick': {} },
        severity: "warn",
        outlined: true,
        disabled: (!__VLS_ctx.accept),
        loading: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_22));
    let __VLS_26;
    const __VLS_27 = ({ click: {} },
        { onClick: (__VLS_ctx.deleteDeployment) });
    const { default: __VLS_28 } = __VLS_24.slots;
    // @ts-ignore
    [accept, loading, deleteDeployment,];
    var __VLS_24;
    var __VLS_25;
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
