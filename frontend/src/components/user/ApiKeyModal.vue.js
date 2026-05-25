/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Dialog, InputGroup, InputGroupAddon, InputText, Button, useToast, useConfirm, } from 'primevue';
import { Copy, Trash2 } from 'lucide-vue-next';
import { computed, ref } from 'vue';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { deleteAPIKeyConfirmOptions } from '@/lib/primevue/data/confirm';
import { useUserStore } from '@/stores/user';
const dialogPt = {
    root: {
        style: 'width: 100%; max-width: 600px',
    },
    header: {
        style: 'text-transform: uppercase; font-size: 20px; padding: 36px 36px 12px;',
    },
    content: {
        style: 'padding: 0 36px;',
    },
    footer: {
        style: 'display: flex; justify-content: flex-end; padding: 28px 36px 36px;',
    },
};
const show = defineModel('show');
const toast = useToast();
const confirm = useConfirm();
const userStore = useUserStore();
const loading = ref(false);
const apiKey = ref(null);
const copyAvailable = computed(() => !!apiKey.value);
const inputValue = computed(() => apiKey.value || 'dfs_***************************************');
async function generate() {
    try {
        loading.value = true;
        apiKey.value = await userStore.createApiKey();
        toast.add(simpleSuccessToast('A new API key has been generated successfully.'));
    }
    catch {
        toast.add(simpleErrorToast('Failed to generate API Key'));
    }
    finally {
        loading.value = false;
    }
}
function copy() {
    if (!apiKey.value)
        return;
    navigator.clipboard.writeText(apiKey.value);
    toast.add(simpleSuccessToast('API key copied to clipboard.'));
}
function onDeleteClick() {
    confirm.require(deleteAPIKeyConfirmOptions(remove));
}
async function remove() {
    try {
        loading.value = true;
        await userStore.deleteApiKey();
        apiKey.value = null;
        toast.add(simpleSuccessToast('API key was deleted.'));
    }
    catch {
        toast.add(simpleErrorToast('Failed to delete API key'));
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
    visible: (__VLS_ctx.show),
    header: "Api key",
    modal: true,
    draggable: (false),
    pt: (__VLS_ctx.dialogPt),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.show),
    header: "Api key",
    modal: true,
    draggable: (false),
    pt: (__VLS_ctx.dialogPt),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
if (__VLS_ctx.userStore.isUserApiKeyExist) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "description" },
    });
    /** @type {__VLS_StyleScopedClasses['description']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "form" },
    });
    /** @type {__VLS_StyleScopedClasses['form']} */ ;
    let __VLS_7;
    /** @ts-ignore @type { | typeof __VLS_components.InputGroup | typeof __VLS_components.InputGroup} */
    InputGroup;
    // @ts-ignore
    const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({}));
    const __VLS_9 = __VLS_8({}, ...__VLS_functionalComponentArgsRest(__VLS_8));
    const { default: __VLS_12 } = __VLS_10.slots;
    let __VLS_13;
    /** @ts-ignore @type { | typeof __VLS_components.InputText} */
    InputText;
    // @ts-ignore
    const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
        ...{ 'onInput': {} },
        placeholder: "Apy key",
        disabled: (!__VLS_ctx.copyAvailable),
        value: (__VLS_ctx.inputValue),
        readonly: true,
    }));
    const __VLS_15 = __VLS_14({
        ...{ 'onInput': {} },
        placeholder: "Apy key",
        disabled: (!__VLS_ctx.copyAvailable),
        value: (__VLS_ctx.inputValue),
        readonly: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_14));
    let __VLS_18;
    const __VLS_19 = ({ input: {} },
        { onInput: () => { } });
    var __VLS_16;
    var __VLS_17;
    if (__VLS_ctx.copyAvailable) {
        let __VLS_20;
        /** @ts-ignore @type { | typeof __VLS_components.InputGroupAddon | typeof __VLS_components.InputGroupAddon} */
        InputGroupAddon;
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({}));
        const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
        const { default: __VLS_25 } = __VLS_23.slots;
        let __VLS_26;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
            ...{ 'onClick': {} },
            variant: "text",
            severity: "secondary",
            size: "small",
            ...{ style: {} },
        }));
        const __VLS_28 = __VLS_27({
            ...{ 'onClick': {} },
            variant: "text",
            severity: "secondary",
            size: "small",
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_27));
        let __VLS_31;
        const __VLS_32 = ({ click: {} },
            { onClick: (__VLS_ctx.copy) });
        const { default: __VLS_33 } = __VLS_29.slots;
        let __VLS_34;
        /** @ts-ignore @type { | typeof __VLS_components.Copy} */
        Copy;
        // @ts-ignore
        const __VLS_35 = __VLS_asFunctionalComponent1(__VLS_34, new __VLS_34({
            size: (14),
        }));
        const __VLS_36 = __VLS_35({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_35));
        // @ts-ignore
        [show, dialogPt, userStore, copyAvailable, copyAvailable, inputValue, copy,];
        var __VLS_29;
        var __VLS_30;
        // @ts-ignore
        [];
        var __VLS_23;
    }
    // @ts-ignore
    [];
    var __VLS_10;
    let __VLS_39;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_40 = __VLS_asFunctionalComponent1(__VLS_39, new __VLS_39({
        ...{ 'onClick': {} },
        severity: "secondary",
        ...{ class: "remove-button" },
        disabled: (__VLS_ctx.loading),
    }));
    const __VLS_41 = __VLS_40({
        ...{ 'onClick': {} },
        severity: "secondary",
        ...{ class: "remove-button" },
        disabled: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_40));
    let __VLS_44;
    const __VLS_45 = ({ click: {} },
        { onClick: (__VLS_ctx.onDeleteClick) });
    /** @type {__VLS_StyleScopedClasses['remove-button']} */ ;
    const { default: __VLS_46 } = __VLS_42.slots;
    {
        const { icon: __VLS_47 } = __VLS_42.slots;
        let __VLS_48;
        /** @ts-ignore @type { | typeof __VLS_components.Trash2} */
        Trash2;
        // @ts-ignore
        const __VLS_49 = __VLS_asFunctionalComponent1(__VLS_48, new __VLS_48({
            size: (14),
        }));
        const __VLS_50 = __VLS_49({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_49));
        // @ts-ignore
        [loading, onDeleteClick,];
    }
    // @ts-ignore
    [];
    var __VLS_42;
    var __VLS_43;
    if (!__VLS_ctx.apiKey) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "message" },
        });
        /** @type {__VLS_StyleScopedClasses['message']} */ ;
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "description" },
    });
    /** @type {__VLS_StyleScopedClasses['description']} */ ;
}
{
    const { footer: __VLS_53 } = __VLS_3.slots;
    let __VLS_54;
    /** @ts-ignore @type { | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_55 = __VLS_asFunctionalComponent1(__VLS_54, new __VLS_54({
        ...{ 'onClick': {} },
        label: (__VLS_ctx.userStore.isUserApiKeyExist ? 'Regenerate key' : 'Generate key'),
        loading: (__VLS_ctx.loading),
    }));
    const __VLS_56 = __VLS_55({
        ...{ 'onClick': {} },
        label: (__VLS_ctx.userStore.isUserApiKeyExist ? 'Regenerate key' : 'Generate key'),
        loading: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_55));
    let __VLS_59;
    const __VLS_60 = ({ click: {} },
        { onClick: (__VLS_ctx.generate) });
    var __VLS_57;
    var __VLS_58;
    // @ts-ignore
    [userStore, loading, apiKey, generate,];
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
