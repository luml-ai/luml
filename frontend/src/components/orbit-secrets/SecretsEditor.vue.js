/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref, watch } from 'vue';
import { Dialog, Button, InputText, AutoComplete, Password, useToast, useConfirm } from 'primevue';
import { Form } from '@primevue/forms';
import { Bolt } from 'lucide-vue-next';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { updateSecretResolver } from '@/utils/forms/resolvers';
import { useSecretsStore } from '@/stores/orbit-secrets';
import { useOrbitsStore } from '@/stores/orbits';
import { deleteSecretConfirmation } from '@/lib/primevue/data/confirm';
const props = defineProps();
const emit = defineEmits(['update:visible']);
const secretsStore = useSecretsStore();
const orbitsStore = useOrbitsStore();
const toast = useToast();
const dialogPt = {
    footer: {
        style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
    },
};
const formData = ref({
    id: props.secret?.id || '',
    name: props.secret?.name || '',
    value: '',
    tags: props.secret?.tags ? [...props.secret.tags] : [],
});
async function loadSecretDetails() {
    if (!props.secret?.id)
        return;
    const orbit = orbitsStore.currentOrbitDetails;
    if (!orbit?.organization_id || !orbit?.id)
        return;
    try {
        const fullSecret = await secretsStore.getSecretById(orbit.organization_id, orbit.id, props.secret.id);
        if (fullSecret) {
            formData.value = {
                id: fullSecret.id,
                name: fullSecret.name || '',
                value: fullSecret.value || '',
                tags: fullSecret.tags ? [...fullSecret.tags] : [],
            };
        }
    }
    catch (error) {
        toast.add(simpleErrorToast('Failed to load secret details'));
    }
}
watch(() => props.secret, async (secret) => {
    if (secret?.id) {
        await loadSecretDetails();
    }
    else {
        formData.value = {
            id: '',
            name: '',
            value: '',
            tags: [],
        };
    }
}, { immediate: true });
watch(() => props.visible, async (visible) => {
    if (visible && props.secret?.id) {
        await loadSecretDetails();
    }
});
const updateLoading = ref(false);
const deleteLoading = ref(false);
const existingTags = computed(() => secretsStore.existingTags);
const autocompleteItems = ref([]);
function searchTags(event) {
    autocompleteItems.value = [
        event.query,
        ...existingTags.value.filter((tag) => tag.toLowerCase().includes(event.query.toLowerCase())),
    ];
}
function getRequestInfo() {
    const orbit = orbitsStore.currentOrbitDetails;
    if (orbit?.organization_id && orbit?.id) {
        return { organizationId: orbit.organization_id, orbitId: orbit.id };
    }
}
async function onSubmit({ valid }) {
    if (!valid || !props.secret)
        return;
    try {
        updateLoading.value = true;
        const req = getRequestInfo();
        if (!req)
            throw new Error('Orbit info is missing');
        const updatePayload = {
            id: props.secret.id,
            name: formData.value.name?.trim() || props.secret.name || '',
            tags: formData.value.tags,
        };
        if (formData.value.value?.trim()) {
            updatePayload.value = formData.value.value.trim();
        }
        await secretsStore.updateSecret(req.organizationId, req.orbitId, updatePayload);
        toast.add(simpleSuccessToast('Secret updated successfully'));
        emit('update:visible', false);
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to update secret'));
    }
    finally {
        updateLoading.value = false;
    }
}
const confirm = useConfirm();
function onComponentDelete() {
    confirm.require({
        ...deleteSecretConfirmation,
        accept: async () => {
            await onDelete();
        },
    });
}
async function onDelete() {
    if (!props.secret)
        return;
    try {
        deleteLoading.value = true;
        const req = getRequestInfo();
        if (!req)
            throw new Error('Orbit info is missing');
        await secretsStore.deleteSecret(req.organizationId, req.orbitId, props.secret.id);
        toast.add(simpleSuccessToast('Secret deleted successfully'));
        emit('update:visible', false);
    }
    catch (e) {
        const errorMessage = e?.response?.data?.detail || e.message || 'Failed to delete secret';
        if (errorMessage.includes('used') ||
            errorMessage.includes('deployment') ||
            errorMessage.includes('active')) {
            toast.add(simpleErrorToast('The secret is currently used by active deployments'));
        }
        else {
            toast.add(simpleErrorToast(errorMessage));
        }
    }
    finally {
        deleteLoading.value = false;
    }
}
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
    ...{ 'onUpdate:visible': {} },
    visible: (props.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPt),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:visible': {} },
    visible: (props.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPt),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ 'update:visible': {} },
    { 'onUpdate:visible': (...[$event]) => {
            __VLS_ctx.emit('update:visible', $event);
            // @ts-ignore
            [dialogPt, emit,];
        } });
var __VLS_7;
const { default: __VLS_8 } = __VLS_3.slots;
{
    const { header: __VLS_9 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "dialog-title" },
    });
    /** @type {__VLS_StyleScopedClasses['dialog-title']} */ ;
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.Bolt} */
    Bolt;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        size: (20),
        color: "var(--p-primary-color)",
    }));
    const __VLS_12 = __VLS_11({
        size: (20),
        color: "var(--p-primary-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [];
}
let __VLS_15;
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    ...{ 'onSubmit': {} },
    id: "secret-edit-form",
    initialValues: (__VLS_ctx.formData),
    resolver: (__VLS_ctx.updateSecretResolver),
    ...{ class: "form" },
    validateOnSubmit: true,
}));
const __VLS_17 = __VLS_16({
    ...{ 'onSubmit': {} },
    id: "secret-edit-form",
    initialValues: (__VLS_ctx.formData),
    resolver: (__VLS_ctx.updateSecretResolver),
    ...{ class: "form" },
    validateOnSubmit: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
let __VLS_20;
const __VLS_21 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onSubmit) });
/** @type {__VLS_StyleScopedClasses['form']} */ ;
const { default: __VLS_22 } = __VLS_18.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form-item" },
});
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "name",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_23;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
    modelValue: (__VLS_ctx.formData.name),
    id: "name",
    name: "name",
    fluid: true,
}));
const __VLS_25 = __VLS_24({
    modelValue: (__VLS_ctx.formData.name),
    id: "name",
    name: "name",
    fluid: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_24));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form-item" },
});
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "value",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_28;
/** @ts-ignore @type { | typeof __VLS_components.Password} */
Password;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
    modelValue: (__VLS_ctx.formData.value),
    id: "value",
    name: "value",
    feedback: (false),
    toggleMask: true,
    fluid: true,
    key: (props.secret?.id),
}));
const __VLS_30 = __VLS_29({
    modelValue: (__VLS_ctx.formData.value),
    id: "value",
    name: "value",
    feedback: (false),
    toggleMask: true,
    fluid: true,
    key: (props.secret?.id),
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form-item" },
});
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "tags",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_33;
/** @ts-ignore @type { | typeof __VLS_components.AutoComplete} */
AutoComplete;
// @ts-ignore
const __VLS_34 = __VLS_asFunctionalComponent1(__VLS_33, new __VLS_33({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.formData.tags),
    id: "tags",
    name: "tags",
    placeholder: "Type to add tags",
    fluid: true,
    multiple: true,
    suggestions: (__VLS_ctx.autocompleteItems),
}));
const __VLS_35 = __VLS_34({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.formData.tags),
    id: "tags",
    name: "tags",
    placeholder: "Type to add tags",
    fluid: true,
    multiple: true,
    suggestions: (__VLS_ctx.autocompleteItems),
}, ...__VLS_functionalComponentArgsRest(__VLS_34));
let __VLS_38;
const __VLS_39 = ({ complete: {} },
    { onComplete: (__VLS_ctx.searchTags) });
var __VLS_36;
var __VLS_37;
// @ts-ignore
[formData, formData, formData, formData, updateSecretResolver, onSubmit, autocompleteItems, searchTags,];
var __VLS_18;
var __VLS_19;
{
    const { footer: __VLS_40 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "footer-actions" },
    });
    /** @type {__VLS_StyleScopedClasses['footer-actions']} */ ;
    let __VLS_41;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_42 = __VLS_asFunctionalComponent1(__VLS_41, new __VLS_41({
        ...{ 'onClick': {} },
        outlined: true,
        severity: "warn",
        loading: (__VLS_ctx.deleteLoading),
    }));
    const __VLS_43 = __VLS_42({
        ...{ 'onClick': {} },
        outlined: true,
        severity: "warn",
        loading: (__VLS_ctx.deleteLoading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_42));
    let __VLS_46;
    const __VLS_47 = ({ click: {} },
        { onClick: (__VLS_ctx.onComponentDelete) });
    const { default: __VLS_48 } = __VLS_44.slots;
    // @ts-ignore
    [deleteLoading, onComponentDelete,];
    var __VLS_44;
    var __VLS_45;
    let __VLS_49;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_50 = __VLS_asFunctionalComponent1(__VLS_49, new __VLS_49({
        type: "submit",
        form: "secret-edit-form",
        loading: (__VLS_ctx.updateLoading),
    }));
    const __VLS_51 = __VLS_50({
        type: "submit",
        form: "secret-edit-form",
        loading: (__VLS_ctx.updateLoading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_50));
    const { default: __VLS_54 } = __VLS_52.slots;
    // @ts-ignore
    [updateLoading,];
    var __VLS_52;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    emits: {},
    __typeProps: {},
});
export default {};
