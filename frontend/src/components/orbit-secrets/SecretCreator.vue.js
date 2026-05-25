/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Dialog, Button, InputText, AutoComplete, Password, useToast } from 'primevue';
import { Form } from '@primevue/forms';
import { ref, computed } from 'vue';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { useSecretsStore } from '@/stores/orbit-secrets';
import { createSecretResolver } from '@/utils/forms/resolvers';
import { useOrbitsStore } from '@/stores/orbits';
const props = defineProps();
const visible = defineModel('visible');
const dialogPt = {
    root: { style: 'max-width: 500px; width: 100%;' },
    header: { style: 'padding: 28px; text-transform: uppercase; font-size: 20px;' },
    content: { style: 'padding: 0 28px 28px;' },
};
const secretsStore = useSecretsStore();
const orbitsStore = useOrbitsStore();
const toast = useToast();
const loading = ref(false);
const getInitialFormData = () => ({
    name: '',
    value: '',
    tags: [],
});
const formData = ref(getInitialFormData());
const existingTags = computed(() => secretsStore.existingTags);
const autocompleteItems = ref([]);
function searchTags(event) {
    autocompleteItems.value = [
        event.query,
        ...existingTags.value.filter((tag) => tag.toLowerCase().includes(event.query.toLowerCase())),
    ];
}
function getRequestInfo() {
    if (props.organizationId && props.orbitId) {
        return { organizationId: props.organizationId, orbitId: props.orbitId };
    }
    const orbit = orbitsStore.currentOrbitDetails;
    if (orbit?.organization_id && orbit?.id) {
        return { organizationId: orbit.organization_id, orbitId: orbit.id };
    }
}
function resetForm() {
    formData.value = getInitialFormData();
}
async function onSubmit({ valid }) {
    if (!valid)
        return;
    try {
        loading.value = true;
        const req = getRequestInfo();
        if (!req)
            throw new Error('Orbit info is missing');
        await secretsStore.addSecret(req.organizationId, req.orbitId, { ...formData.value });
        visible.value = false;
        resetForm();
        toast.add(simpleSuccessToast('Secret created successfully'));
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to create secret'));
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
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    visible: (__VLS_ctx.visible),
    header: "Create a new secret",
    modal: true,
    draggable: (false),
    pt: (__VLS_ctx.dialogPt),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    header: "Create a new secret",
    modal: true,
    draggable: (false),
    pt: (__VLS_ctx.dialogPt),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
let __VLS_7;
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
    ...{ 'onSubmit': {} },
    initialValues: (__VLS_ctx.formData),
    resolver: (__VLS_ctx.createSecretResolver),
    ...{ class: "form" },
}));
const __VLS_9 = __VLS_8({
    ...{ 'onSubmit': {} },
    initialValues: (__VLS_ctx.formData),
    resolver: (__VLS_ctx.createSecretResolver),
    ...{ class: "form" },
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
let __VLS_12;
const __VLS_13 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onSubmit) });
/** @type {__VLS_StyleScopedClasses['form']} */ ;
const { default: __VLS_14 } = __VLS_10.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form-item" },
});
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "name",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_15;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    modelValue: (__VLS_ctx.formData.name),
    id: "name",
    name: "name",
    placeholder: "Name your secret key",
    fluid: true,
}));
const __VLS_17 = __VLS_16({
    modelValue: (__VLS_ctx.formData.name),
    id: "name",
    name: "name",
    placeholder: "Name your secret key",
    fluid: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form-item" },
});
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "value",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.Password} */
Password;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    modelValue: (__VLS_ctx.formData.value),
    id: "value",
    name: "value",
    feedback: (false),
    placeholder: "Enter secret key",
    toggleMask: true,
    fluid: true,
}));
const __VLS_22 = __VLS_21({
    modelValue: (__VLS_ctx.formData.value),
    id: "value",
    name: "value",
    feedback: (false),
    placeholder: "Enter secret key",
    toggleMask: true,
    fluid: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form-item" },
});
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "tags",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_25;
/** @ts-ignore @type { | typeof __VLS_components.AutoComplete} */
AutoComplete;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.formData.tags),
    id: "tags",
    name: "tags",
    fluid: true,
    multiple: true,
    placeholder: "Type to add tags",
    suggestions: (__VLS_ctx.autocompleteItems),
}));
const __VLS_27 = __VLS_26({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.formData.tags),
    id: "tags",
    name: "tags",
    fluid: true,
    multiple: true,
    placeholder: "Type to add tags",
    suggestions: (__VLS_ctx.autocompleteItems),
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
let __VLS_30;
const __VLS_31 = ({ complete: {} },
    { onComplete: (__VLS_ctx.searchTags) });
var __VLS_28;
var __VLS_29;
let __VLS_32;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
    type: "submit",
    fluid: true,
    rounded: true,
    loading: (__VLS_ctx.loading),
}));
const __VLS_34 = __VLS_33({
    type: "submit",
    fluid: true,
    rounded: true,
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
const { default: __VLS_37 } = __VLS_35.slots;
// @ts-ignore
[visible, dialogPt, formData, formData, formData, formData, createSecretResolver, onSubmit, autocompleteItems, searchTags, loading,];
var __VLS_35;
// @ts-ignore
[];
var __VLS_10;
var __VLS_11;
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
