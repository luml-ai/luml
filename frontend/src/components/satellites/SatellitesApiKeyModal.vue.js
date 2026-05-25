/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Dialog, InputText, InputGroup, InputGroupAddon, Button, useToast } from 'primevue';
import { Copy, CopyCheck } from 'lucide-vue-next';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { computed, ref, watch } from 'vue';
import { useSatellitesStore } from '@/stores/satellites';
import { useRoute } from 'vue-router';
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
const toast = useToast();
const route = useRoute();
const satellitesStore = useSatellitesStore();
const props = defineProps();
const visible = defineModel('visible');
const currentApiKey = ref(null);
const loading = ref(false);
const isCopied = ref(false);
const organizationId = computed(() => {
    const param = route.params.organizationId;
    if (!param)
        throw new Error('Current organization was not found');
    return typeof param === 'string' ? param : param[0];
});
const orbitId = computed(() => {
    const param = route.params.id;
    if (!param)
        throw new Error('Current orbit was not found');
    return typeof param === 'string' ? param : param[0];
});
const copyAvailable = computed(() => !!currentApiKey.value);
const inputValue = computed(() => {
    if (!currentApiKey.value)
        return 'sat_***************************************';
    if (currentApiKey.value.length > 20) {
        return currentApiKey.value.slice(0, 10) + '*******************' + currentApiKey.value.slice(-10);
    }
    else {
        return currentApiKey.value;
    }
});
function copy() {
    if (!currentApiKey.value)
        return;
    navigator.clipboard.writeText(currentApiKey.value);
    toast.add(simpleSuccessToast('API key copied to clipboard.'));
    isCopied.value = true;
    setTimeout(() => {
        isCopied.value = false;
    }, 1000);
}
async function generate() {
    try {
        loading.value = true;
        const { key } = await satellitesStore.regenerateApiKey(organizationId.value, orbitId.value, props.satelliteId);
        currentApiKey.value = key;
        toast.add(simpleSuccessToast('A new API key has been generated successfully.'));
    }
    catch {
        toast.add(simpleErrorToast('Failed to generate API Key'));
    }
    finally {
        loading.value = false;
    }
}
watch(() => props.apiKey, (val) => {
    if (val) {
        currentApiKey.value = val;
    }
}, { immediate: true });
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
    header: "Connect a new satellite",
    pt: (__VLS_ctx.dialogPt),
    modal: true,
    draggable: (false),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    header: "Connect a new satellite",
    pt: (__VLS_ctx.dialogPt),
    modal: true,
    draggable: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text" },
});
/** @type {__VLS_StyleScopedClasses['text']} */ ;
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
    value: (__VLS_ctx.inputValue),
    disabled: (!__VLS_ctx.copyAvailable),
    readonly: true,
}));
const __VLS_15 = __VLS_14({
    ...{ 'onInput': {} },
    placeholder: "Apy key",
    value: (__VLS_ctx.inputValue),
    disabled: (!__VLS_ctx.copyAvailable),
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
    const __VLS_34 = (__VLS_ctx.isCopied ? __VLS_ctx.CopyCheck : __VLS_ctx.Copy);
    // @ts-ignore
    const __VLS_35 = __VLS_asFunctionalComponent1(__VLS_34, new __VLS_34({
        size: (14),
    }));
    const __VLS_36 = __VLS_35({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_35));
    // @ts-ignore
    [visible, dialogPt, inputValue, copyAvailable, copyAvailable, copy, isCopied, CopyCheck, Copy,];
    var __VLS_29;
    var __VLS_30;
    // @ts-ignore
    [];
    var __VLS_23;
}
// @ts-ignore
[];
var __VLS_10;
if (!__VLS_ctx.currentApiKey) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "message" },
    });
    /** @type {__VLS_StyleScopedClasses['message']} */ ;
}
{
    const { footer: __VLS_39 } = __VLS_3.slots;
    if (!__VLS_ctx.currentApiKey) {
        let __VLS_40;
        /** @ts-ignore @type { | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
            ...{ 'onClick': {} },
            label: "Regenerate key",
            loading: (__VLS_ctx.loading),
        }));
        const __VLS_42 = __VLS_41({
            ...{ 'onClick': {} },
            label: "Regenerate key",
            loading: (__VLS_ctx.loading),
        }, ...__VLS_functionalComponentArgsRest(__VLS_41));
        let __VLS_45;
        const __VLS_46 = ({ click: {} },
            { onClick: (__VLS_ctx.generate) });
        var __VLS_43;
        var __VLS_44;
    }
    // @ts-ignore
    [currentApiKey, currentApiKey, loading, generate,];
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
