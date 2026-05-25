/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { Checkbox, Button, Dialog, useToast } from 'primevue';
import { useOrganizationStore } from '@/stores/organization';
import { useRouter } from 'vue-router';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
const organizationStore = useOrganizationStore();
const toast = useToast();
const router = useRouter();
const visible = ref(false);
const accept = ref(false);
const loading = ref(false);
async function deleteOrganization() {
    if (!organizationStore.currentOrganization)
        return;
    try {
        loading.value = true;
        await organizationStore.deleteOrganization(organizationStore.currentOrganization.id);
        router.push({ name: 'home' });
        organizationStore.resetCurrentOrganization();
        toast.add(simpleSuccessToast('The organization and all associated data have been permanently removed.'));
    }
    catch (e) {
        toast.add(simpleErrorToast(e.message || 'Could not delete organization'));
    }
    finally {
        loading.value = false;
    }
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    severity: "warn",
    variant: "outlined",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    severity: "warn",
    variant: "outlined",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.visible = true;
            // @ts-ignore
            [visible,];
        } });
const { default: __VLS_7 } = __VLS_3.slots;
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    visible: (__VLS_ctx.visible),
    modal: true,
    draggable: (false),
    header: "Delete this organization?",
    ...{ style: ({ width: '350px' }) },
}));
const __VLS_10 = __VLS_9({
    visible: (__VLS_ctx.visible),
    modal: true,
    draggable: (false),
    header: "Delete this organization?",
    ...{ style: ({ width: '350px' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
const { default: __VLS_13 } = __VLS_11.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text" },
});
/** @type {__VLS_StyleScopedClasses['text']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center gap-2" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
let __VLS_14;
/** @ts-ignore @type { | typeof __VLS_components.Checkbox} */
Checkbox;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
    modelValue: (__VLS_ctx.accept),
    inputId: "deleteAccept",
    binary: true,
}));
const __VLS_16 = __VLS_15({
    modelValue: (__VLS_ctx.accept),
    inputId: "deleteAccept",
    binary: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "deleteAccept",
});
{
    const { footer: __VLS_19 } = __VLS_11.slots;
    let __VLS_20;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.loading),
    }));
    const __VLS_22 = __VLS_21({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    let __VLS_25;
    const __VLS_26 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.visible = false;
                // @ts-ignore
                [visible, visible, accept, loading,];
            } });
    const { default: __VLS_27 } = __VLS_23.slots;
    // @ts-ignore
    [];
    var __VLS_23;
    var __VLS_24;
    let __VLS_28;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
        ...{ 'onClick': {} },
        severity: "warn",
        outlined: true,
        disabled: (!__VLS_ctx.accept),
        loading: (__VLS_ctx.loading),
    }));
    const __VLS_30 = __VLS_29({
        ...{ 'onClick': {} },
        severity: "warn",
        outlined: true,
        disabled: (!__VLS_ctx.accept),
        loading: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    let __VLS_33;
    const __VLS_34 = ({ click: {} },
        { onClick: (__VLS_ctx.deleteOrganization) });
    const { default: __VLS_35 } = __VLS_31.slots;
    // @ts-ignore
    [accept, loading, deleteOrganization,];
    var __VLS_31;
    var __VLS_32;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_11;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
