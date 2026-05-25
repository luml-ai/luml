/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, watch } from 'vue';
import { Dialog, InputText, InputGroup, InputGroupAddon, Button, useToast } from 'primevue';
import { Copy } from 'lucide-vue-next';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { useSecretsStore } from '@/stores/orbit-secrets';
import { useOrbitsStore } from '@/stores/orbits';
const props = defineProps();
const visible = defineModel('visible');
const toast = useToast();
const secretsStore = useSecretsStore();
const orbitsStore = useOrbitsStore();
const secretValue = ref('');
const loading = ref(false);
watch(visible, (val) => {
    if (val && props.secret)
        loadSecretValue(props.secret.id);
});
const dialogPt = {
    mask: {
        style: 'padding: 15px;',
    },
    root: {
        style: 'width: 600px;',
    },
    header: {
        style: 'text-transform: uppercase; padding: 36px 36px 28px;',
    },
    content: {
        style: 'padding: 0 36px 36px;',
    },
    footer: {
        style: 'display: flex; justify-content: flex-end; padding: 0 36px 36px;',
    },
};
async function loadSecretValue(secretId) {
    const orbit = orbitsStore.currentOrbitDetails;
    if (!orbit?.organization_id || !orbit?.id)
        return;
    try {
        loading.value = true;
        const fullSecret = await secretsStore.getSecretById(orbit.organization_id, orbit.id, secretId);
        secretValue.value = fullSecret?.value || '';
    }
    catch (error) {
        toast.add(simpleErrorToast('You don’t have access to view this key.'));
    }
    finally {
        loading.value = false;
    }
}
async function copySecret() {
    if (!secretValue.value)
        return;
    try {
        await navigator.clipboard.writeText(secretValue.value);
        toast.add(simpleSuccessToast('Secret copied to clipboard'));
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to copy secret'));
        console.error('Copy secret error:', e);
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
    header: "Key",
    pt: (__VLS_ctx.dialogPt),
    modal: true,
    draggable: (false),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    header: "Key",
    pt: (__VLS_ctx.dialogPt),
    modal: true,
    draggable: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
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
    value: (__VLS_ctx.loading ? 'Loading...' : __VLS_ctx.secretValue),
    disabled: (__VLS_ctx.loading),
    readonly: true,
}));
const __VLS_15 = __VLS_14({
    value: (__VLS_ctx.loading ? 'Loading...' : __VLS_ctx.secretValue),
    disabled: (__VLS_ctx.loading),
    readonly: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
let __VLS_18;
/** @ts-ignore @type { | typeof __VLS_components.InputGroupAddon | typeof __VLS_components.InputGroupAddon} */
InputGroupAddon;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({}));
const __VLS_20 = __VLS_19({}, ...__VLS_functionalComponentArgsRest(__VLS_19));
const { default: __VLS_23 } = __VLS_21.slots;
let __VLS_24;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
    ...{ style: {} },
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_29;
const __VLS_30 = ({ click: {} },
    { onClick: (__VLS_ctx.copySecret) });
const { default: __VLS_31 } = __VLS_27.slots;
let __VLS_32;
/** @ts-ignore @type { | typeof __VLS_components.Copy} */
Copy;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
    size: (14),
}));
const __VLS_34 = __VLS_33({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
// @ts-ignore
[visible, dialogPt, loading, loading, secretValue, copySecret,];
var __VLS_27;
var __VLS_28;
// @ts-ignore
[];
var __VLS_21;
// @ts-ignore
[];
var __VLS_10;
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
