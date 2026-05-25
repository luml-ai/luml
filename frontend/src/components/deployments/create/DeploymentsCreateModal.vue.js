/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Dialog, Button, useToast } from 'primevue';
import { Form } from '@primevue/forms';
import { dialogPt, getInitialFormData } from '../deployments.const';
import { computed, ref } from 'vue';
import { createDeploymentResolver } from '@/utils/forms/resolvers';
import { getErrorMessage } from '@/helpers/helpers';
import { useCollectionsStore } from '@/stores/collections';
import { useDeploymentsStore } from '@/stores/deployments';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import DeploymentsFormBasicsSettings from '../form/DeploymentsFormBasicsSettings.vue';
import DeploymentsFormModelSettings from '../form/model-settings/DeploymentsFormModelSettings.vue';
import DeploymentsFormSatelliteSettings from '../form/DeploymentsFormSatelliteSettings.vue';
const props = defineProps();
const collectionsStore = useCollectionsStore();
const deploymentsStore = useDeploymentsStore();
const toast = useToast();
const visible = defineModel('visible');
const formRef = ref();
const loading = ref(false);
const selectedModel = ref(null);
const initialValues = ref(getInitialFormData(props.initialCollectionId, props.initialModelId));
const resolver = ref(createDeploymentResolver(initialValues));
function areFieldsFilled(fields) {
    if (!fields || fields.length === 0)
        return true;
    return fields.every((field) => field.value !== null && field.value !== '' && field.value !== undefined);
}
const isFormValid = computed(() => {
    const form = initialValues.value;
    const basicFieldsValid = !!(form.name && form.collectionId && form.modelId && form.satelliteId);
    if (!basicFieldsValid)
        return false;
    return (areFieldsFilled(form.secretEnvs) &&
        areFieldsFilled(form.notSecretEnvs) &&
        areFieldsFilled(form.secretDynamicAttributes) &&
        areFieldsFilled(form.satelliteFields));
});
function onCancel() {
    visible.value = false;
}
function resetForm() {
    initialValues.value = getInitialFormData();
}
async function onSubmit({ valid }) {
    if (!valid) {
        toast.add(simpleErrorToast('Check the form for errors'));
        return;
    }
    const formData = initialValues.value;
    const payload = getPayload(formData);
    try {
        loading.value = true;
        await deploymentsStore.createDeployment(collectionsStore.requestInfo.organizationId, collectionsStore.requestInfo.orbitId, payload);
        visible.value = false;
        toast.add({
            severity: 'success',
            summary: 'Success',
            detail: `Deployment ${payload.name} was successfully created.<br><a href="#" class="toast-action-link" data-route="orbit-deployments" data-params="{}">Go to Deployments</a>`,
            life: 5000,
        });
    }
    catch (e) {
        toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to create deployment')));
    }
    finally {
        loading.value = false;
    }
}
function getPayload(form) {
    return {
        name: form.name,
        description: form.description,
        satellite_id: form.satelliteId,
        artifact_id: form.modelId,
        satellite_parameters: fieldsToRecord(form.satelliteFields, (v) => v),
        dynamic_attributes_secrets: fieldsToRecord(form.secretDynamicAttributes, (v) => v),
        env_variables_secrets: fieldsToRecord(form.secretEnvs, (v) => String(v)),
        env_variables: fieldsToRecord(form.notSecretEnvs, (v) => String(v)),
        tags: form.tags,
    };
}
function fieldsToRecord(fields, transform) {
    return fields.reduce((acc, { key, value }) => {
        if (value === null)
            return acc;
        acc[key] = transform(value);
        return acc;
    }, {});
}
function onModelChanged(model) {
    selectedModel.value = model;
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
/** @type {__VLS_StyleScopedClasses['content']} */ ;
/** @type {__VLS_StyleScopedClasses['header-content']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    visible: (__VLS_ctx.visible),
    pt: (__VLS_ctx.dialogPt),
    modal: true,
    draggable: (false),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    pt: (__VLS_ctx.dialogPt),
    modal: true,
    draggable: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
{
    const { header: __VLS_7 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "header-content" },
    });
    /** @type {__VLS_StyleScopedClasses['header-content']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "buttons" },
    });
    /** @type {__VLS_StyleScopedClasses['buttons']} */ ;
    let __VLS_8;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        form: "createDeploymentForm",
        label: "Deploy",
        disabled: (!__VLS_ctx.isFormValid),
        loading: (__VLS_ctx.loading),
        type: "submit",
    }));
    const __VLS_10 = __VLS_9({
        form: "createDeploymentForm",
        label: "Deploy",
        disabled: (!__VLS_ctx.isFormValid),
        loading: (__VLS_ctx.loading),
        type: "submit",
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_13;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
        ...{ 'onClick': {} },
        label: "Cancel",
        severity: "secondary",
    }));
    const __VLS_15 = __VLS_14({
        ...{ 'onClick': {} },
        label: "Cancel",
        severity: "secondary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_14));
    let __VLS_18;
    const __VLS_19 = ({ click: {} },
        { onClick: (__VLS_ctx.onCancel) });
    var __VLS_16;
    var __VLS_17;
    // @ts-ignore
    [visible, dialogPt, isFormValid, loading, onCancel,];
}
{
    const { default: __VLS_20 } = __VLS_3.slots;
    if (__VLS_ctx.visible) {
        let __VLS_21;
        /** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
        Form;
        // @ts-ignore
        const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
            ...{ 'onSubmit': {} },
            ref: "formRef",
            id: "createDeploymentForm",
            ...{ class: "content" },
            initialValues: (__VLS_ctx.initialValues),
            resolver: (__VLS_ctx.resolver),
        }));
        const __VLS_23 = __VLS_22({
            ...{ 'onSubmit': {} },
            ref: "formRef",
            id: "createDeploymentForm",
            ...{ class: "content" },
            initialValues: (__VLS_ctx.initialValues),
            resolver: (__VLS_ctx.resolver),
        }, ...__VLS_functionalComponentArgsRest(__VLS_22));
        let __VLS_26;
        const __VLS_27 = ({ submit: {} },
            { onSubmit: (__VLS_ctx.onSubmit) });
        var __VLS_28;
        /** @type {__VLS_StyleScopedClasses['content']} */ ;
        const { default: __VLS_30 } = __VLS_24.slots;
        const __VLS_31 = DeploymentsFormBasicsSettings || DeploymentsFormBasicsSettings;
        // @ts-ignore
        const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
            description: (__VLS_ctx.initialValues.description),
            name: (__VLS_ctx.initialValues.name),
            tags: (__VLS_ctx.initialValues.tags),
        }));
        const __VLS_33 = __VLS_32({
            description: (__VLS_ctx.initialValues.description),
            name: (__VLS_ctx.initialValues.name),
            tags: (__VLS_ctx.initialValues.tags),
        }, ...__VLS_functionalComponentArgsRest(__VLS_32));
        const __VLS_36 = DeploymentsFormModelSettings || DeploymentsFormModelSettings;
        // @ts-ignore
        const __VLS_37 = __VLS_asFunctionalComponent1(__VLS_36, new __VLS_36({
            ...{ 'onModelChanged': {} },
            initialCollectionId: (__VLS_ctx.initialCollectionId),
            initialModelId: (__VLS_ctx.initialModelId),
            collectionId: (__VLS_ctx.initialValues.collectionId),
            modelId: (__VLS_ctx.initialValues.modelId),
            secretDynamicAttributes: (__VLS_ctx.initialValues.secretDynamicAttributes),
            dynamicAttributes: (__VLS_ctx.initialValues.dynamicAttributes),
            secretEnvs: (__VLS_ctx.initialValues.secretEnvs),
            notSecretEnvs: (__VLS_ctx.initialValues.notSecretEnvs),
            customVariables: (__VLS_ctx.initialValues.customVariables),
        }));
        const __VLS_38 = __VLS_37({
            ...{ 'onModelChanged': {} },
            initialCollectionId: (__VLS_ctx.initialCollectionId),
            initialModelId: (__VLS_ctx.initialModelId),
            collectionId: (__VLS_ctx.initialValues.collectionId),
            modelId: (__VLS_ctx.initialValues.modelId),
            secretDynamicAttributes: (__VLS_ctx.initialValues.secretDynamicAttributes),
            dynamicAttributes: (__VLS_ctx.initialValues.dynamicAttributes),
            secretEnvs: (__VLS_ctx.initialValues.secretEnvs),
            notSecretEnvs: (__VLS_ctx.initialValues.notSecretEnvs),
            customVariables: (__VLS_ctx.initialValues.customVariables),
        }, ...__VLS_functionalComponentArgsRest(__VLS_37));
        let __VLS_41;
        const __VLS_42 = ({ modelChanged: {} },
            { onModelChanged: (__VLS_ctx.onModelChanged) });
        var __VLS_39;
        var __VLS_40;
        const __VLS_43 = DeploymentsFormSatelliteSettings || DeploymentsFormSatelliteSettings;
        // @ts-ignore
        const __VLS_44 = __VLS_asFunctionalComponent1(__VLS_43, new __VLS_43({
            selectedModel: (__VLS_ctx.selectedModel),
            satelliteId: (__VLS_ctx.initialValues.satelliteId),
            fields: (__VLS_ctx.initialValues.satelliteFields),
        }));
        const __VLS_45 = __VLS_44({
            selectedModel: (__VLS_ctx.selectedModel),
            satelliteId: (__VLS_ctx.initialValues.satelliteId),
            fields: (__VLS_ctx.initialValues.satelliteFields),
        }, ...__VLS_functionalComponentArgsRest(__VLS_44));
        // @ts-ignore
        [visible, initialValues, initialValues, initialValues, initialValues, initialValues, initialValues, initialValues, initialValues, initialValues, initialValues, initialValues, initialValues, initialValues, resolver, onSubmit, initialCollectionId, initialModelId, onModelChanged, selectedModel,];
        var __VLS_24;
        var __VLS_25;
    }
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
var __VLS_29 = __VLS_28;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
