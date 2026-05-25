/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Dialog, Button, useToast, Accordion, AccordionPanel, AccordionHeader, AccordionContent, } from 'primevue';
import { DeploymentStatusEnum, } from '@/lib/api/deployments/interfaces';
import { computed, onBeforeMount, ref } from 'vue';
import { ChevronDown, ChevronUp, HelpCircle, Rocket } from 'lucide-vue-next';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { createDeploymentResolver } from '@/utils/forms/resolvers';
import { Form, FormField } from '@primevue/forms';
import { useCollectionsStore } from '@/stores/collections';
import { useSecretsStore } from '@/stores/orbit-secrets';
import { useArtifactsStore } from '@/stores/artifacts';
import { useRoute } from 'vue-router';
import { FnnxService } from '@/lib/fnnx/FnnxService';
import { useDeploymentsStore } from '@/stores/deployments';
import { editorDialogPt } from '../deployments.const';
import { getErrorMessage } from '@/helpers/helpers';
import DeploymentsFormBasicsSettings from '../form/DeploymentsFormBasicsSettings.vue';
import DeploymentsDelete from '@/components/orbits/delete/DeploymentsDelete.vue';
import SecretsSelect from '../form/SecretsSelect.vue';
import ForceDeleteConfirmDialog from '@/components/ui/dialogs/ForceDeleteConfirmDialog.vue';
const FORCE_DELETE_TEXT = 'This action will schedule a task for your satellite to shut down this deployment. <br /> If you are sure, then write "delete" below';
const props = defineProps();
const visible = defineModel('visible');
const toast = useToast();
const collectionsStore = useCollectionsStore();
const secretsStore = useSecretsStore();
const artifactsStore = useArtifactsStore();
const route = useRoute();
const deploymentsStore = useDeploymentsStore();
const isDeleting = ref(false);
const isForceDeleting = ref(false);
const initialValues = ref({
    name: props.data.name,
    description: props.data.description,
    tags: props.data.tags,
    collectionId: props.data.collection_id,
    modelId: props.data.artifact_id,
    secretDynamicAttributes: [],
});
const loading = ref(false);
const organizationId = computed(() => {
    if (typeof route.params.organizationId !== 'string')
        throw new Error('Incorrect organization ID');
    return route.params.organizationId;
});
const isForceDelete = computed(() => {
    return DeploymentStatusEnum.active !== props.data.status;
});
async function saveChanges() {
    try {
        loading.value = true;
        const dynamic_attributes_secrets = initialValues.value.secretDynamicAttributes.reduce((acc, attribute) => {
            if (!attribute.value)
                return acc;
            acc[attribute.key] = attribute.value;
            return acc;
        }, {});
        const payload = {
            name: initialValues.value.name,
            description: initialValues.value.description,
            tags: initialValues.value.tags,
            dynamic_attributes_secrets,
        };
        await deploymentsStore.update(organizationId.value, props.data.orbit_id, props.data.id, payload);
        toast.add(simpleSuccessToast('Deployment changes saved successfully.'));
        visible.value = false;
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to update deployment'));
    }
    finally {
        loading.value = false;
    }
}
function onDeleteClick() {
    isDeleting.value = true;
}
function onForceDeleteClick() {
    isForceDeleting.value = true;
}
async function onForceDelete() {
    try {
        loading.value = true;
        await deploymentsStore.forceDeleteDeployment(organizationId.value, props.data.orbit_id, props.data.id);
        toast.add(simpleSuccessToast('Deployment is being deleted.'));
        isForceDeleting.value = false;
        visible.value = false;
    }
    catch (e) {
        toast.add(simpleErrorToast(getErrorMessage(e, 'Could not force delete deployment')));
    }
    finally {
        loading.value = false;
    }
}
function onDelete() {
    isDeleting.value = false;
    visible.value = false;
}
function setSecrets(secrets) {
    initialValues.value.secretDynamicAttributes = secrets.map((attribute) => {
        const existingValue = props.data.dynamic_attributes_secrets[attribute.name];
        return {
            key: attribute.name,
            label: attribute.description || attribute.name,
            value: existingValue || null,
        };
    });
}
onBeforeMount(async () => {
    try {
        await secretsStore.loadSecrets(organizationId.value, props.data.orbit_id);
        const requestInfo = {
            organizationId: organizationId.value,
            orbitId: props.data.orbit_id,
            collectionId: props.data.collection_id,
        };
        const currentModel = await artifactsStore.getArtifact(props.data.artifact_id, requestInfo);
        if (!currentModel)
            return;
        const { secrets } = FnnxService.getDynamicAttributes(currentModel.manifest);
        setSecrets(secrets);
    }
    catch (e) {
        toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load model')));
    }
});
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
/** @type {__VLS_StyleScopedClasses['p-accordioncontent-content']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    visible: (__VLS_ctx.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.editorDialogPt),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.editorDialogPt),
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
    /** @ts-ignore @type { | typeof __VLS_components.Rocket} */
    Rocket;
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
    [visible, editorDialogPt,];
}
if (__VLS_ctx.visible) {
    let __VLS_13;
    /** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
    Form;
    // @ts-ignore
    const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
        ...{ 'onSubmit': {} },
        ref: "formRef",
        id: "createDeploymentForm",
        ...{ class: "content" },
        initialValues: (__VLS_ctx.initialValues),
        resolver: (__VLS_ctx.createDeploymentResolver),
    }));
    const __VLS_15 = __VLS_14({
        ...{ 'onSubmit': {} },
        ref: "formRef",
        id: "createDeploymentForm",
        ...{ class: "content" },
        initialValues: (__VLS_ctx.initialValues),
        resolver: (__VLS_ctx.createDeploymentResolver),
    }, ...__VLS_functionalComponentArgsRest(__VLS_14));
    let __VLS_18;
    const __VLS_19 = ({ submit: {} },
        { onSubmit: (__VLS_ctx.saveChanges) });
    var __VLS_20;
    /** @type {__VLS_StyleScopedClasses['content']} */ ;
    const { default: __VLS_22 } = __VLS_16.slots;
    const __VLS_23 = DeploymentsFormBasicsSettings || DeploymentsFormBasicsSettings;
    // @ts-ignore
    const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
        description: (__VLS_ctx.initialValues.description),
        name: (__VLS_ctx.initialValues.name),
        tags: (__VLS_ctx.initialValues.tags),
        showTitle: (false),
        ...{ class: "base-settings" },
    }));
    const __VLS_25 = __VLS_24({
        description: (__VLS_ctx.initialValues.description),
        name: (__VLS_ctx.initialValues.name),
        tags: (__VLS_ctx.initialValues.tags),
        showTitle: (false),
        ...{ class: "base-settings" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_24));
    /** @type {__VLS_StyleScopedClasses['base-settings']} */ ;
    if (__VLS_ctx.initialValues.secretDynamicAttributes.length) {
        let __VLS_28;
        /** @ts-ignore @type { | typeof __VLS_components.Accordion | typeof __VLS_components.Accordion} */
        Accordion;
        // @ts-ignore
        const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
            ...{ style: {} },
        }));
        const __VLS_30 = __VLS_29({
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_29));
        const { default: __VLS_33 } = __VLS_31.slots;
        {
            const { expandicon: __VLS_34 } = __VLS_31.slots;
            let __VLS_35;
            /** @ts-ignore @type { | typeof __VLS_components.ChevronDown | typeof __VLS_components.ChevronDown} */
            ChevronDown;
            // @ts-ignore
            const __VLS_36 = __VLS_asFunctionalComponent1(__VLS_35, new __VLS_35({
                size: (20),
            }));
            const __VLS_37 = __VLS_36({
                size: (20),
            }, ...__VLS_functionalComponentArgsRest(__VLS_36));
            // @ts-ignore
            [visible, initialValues, initialValues, initialValues, initialValues, initialValues, createDeploymentResolver, saveChanges,];
        }
        {
            const { collapseicon: __VLS_40 } = __VLS_31.slots;
            let __VLS_41;
            /** @ts-ignore @type { | typeof __VLS_components.ChevronUp | typeof __VLS_components.ChevronUp} */
            ChevronUp;
            // @ts-ignore
            const __VLS_42 = __VLS_asFunctionalComponent1(__VLS_41, new __VLS_41({
                size: (20),
            }));
            const __VLS_43 = __VLS_42({
                size: (20),
            }, ...__VLS_functionalComponentArgsRest(__VLS_42));
            // @ts-ignore
            [];
        }
        let __VLS_46;
        /** @ts-ignore @type { | typeof __VLS_components.AccordionPanel | typeof __VLS_components.AccordionPanel} */
        AccordionPanel;
        // @ts-ignore
        const __VLS_47 = __VLS_asFunctionalComponent1(__VLS_46, new __VLS_46({
            value: "0",
        }));
        const __VLS_48 = __VLS_47({
            value: "0",
        }, ...__VLS_functionalComponentArgsRest(__VLS_47));
        const { default: __VLS_51 } = __VLS_49.slots;
        let __VLS_52;
        /** @ts-ignore @type { | typeof __VLS_components.AccordionHeader | typeof __VLS_components.AccordionHeader} */
        AccordionHeader;
        // @ts-ignore
        const __VLS_53 = __VLS_asFunctionalComponent1(__VLS_52, new __VLS_52({}));
        const __VLS_54 = __VLS_53({}, ...__VLS_functionalComponentArgsRest(__VLS_53));
        const { default: __VLS_57 } = __VLS_55.slots;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "accordion-title" },
        });
        /** @type {__VLS_StyleScopedClasses['accordion-title']} */ ;
        let __VLS_58;
        /** @ts-ignore @type { | typeof __VLS_components.HelpCircle | typeof __VLS_components.HelpCircle} */
        HelpCircle;
        // @ts-ignore
        const __VLS_59 = __VLS_asFunctionalComponent1(__VLS_58, new __VLS_58({
            size: (12),
            color: "var(--p-button-text-secondary-color)",
        }));
        const __VLS_60 = __VLS_59({
            size: (12),
            color: "var(--p-button-text-secondary-color)",
        }, ...__VLS_functionalComponentArgsRest(__VLS_59));
        // @ts-ignore
        [];
        var __VLS_55;
        let __VLS_63;
        /** @ts-ignore @type { | typeof __VLS_components.AccordionContent | typeof __VLS_components.AccordionContent} */
        AccordionContent;
        // @ts-ignore
        const __VLS_64 = __VLS_asFunctionalComponent1(__VLS_63, new __VLS_63({}));
        const __VLS_65 = __VLS_64({}, ...__VLS_functionalComponentArgsRest(__VLS_64));
        const { default: __VLS_68 } = __VLS_66.slots;
        for (const [secret, index] of __VLS_vFor((__VLS_ctx.initialValues.secretDynamicAttributes))) {
            let __VLS_69;
            /** @ts-ignore @type { | typeof __VLS_components.FormField | typeof __VLS_components.FormField} */
            FormField;
            // @ts-ignore
            const __VLS_70 = __VLS_asFunctionalComponent1(__VLS_69, new __VLS_69({
                key: (secret.key),
                name: (`secretDynamicAttributes.${index}.value`),
                ...{ class: "field" },
            }));
            const __VLS_71 = __VLS_70({
                key: (secret.key),
                name: (`secretDynamicAttributes.${index}.value`),
                ...{ class: "field" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_70));
            /** @type {__VLS_StyleScopedClasses['field']} */ ;
            const { default: __VLS_74 } = __VLS_72.slots;
            __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
                ...{ class: "label" },
            });
            /** @type {__VLS_StyleScopedClasses['label']} */ ;
            (secret.label);
            const __VLS_75 = SecretsSelect || SecretsSelect;
            // @ts-ignore
            const __VLS_76 = __VLS_asFunctionalComponent1(__VLS_75, new __VLS_75({
                modelValue: (secret.value),
                secretsList: (__VLS_ctx.secretsStore.secretsList),
            }));
            const __VLS_77 = __VLS_76({
                modelValue: (secret.value),
                secretsList: (__VLS_ctx.secretsStore.secretsList),
            }, ...__VLS_functionalComponentArgsRest(__VLS_76));
            // @ts-ignore
            [initialValues, secretsStore,];
            var __VLS_72;
            // @ts-ignore
            [];
        }
        // @ts-ignore
        [];
        var __VLS_66;
        // @ts-ignore
        [];
        var __VLS_49;
        // @ts-ignore
        [];
        var __VLS_31;
    }
    // @ts-ignore
    [];
    var __VLS_16;
    var __VLS_17;
}
{
    const { footer: __VLS_80 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    if (__VLS_ctx.isForceDelete) {
        let __VLS_81;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_82 = __VLS_asFunctionalComponent1(__VLS_81, new __VLS_81({
            ...{ 'onClick': {} },
            variant: "outlined",
            severity: "warn",
            disabled: (__VLS_ctx.loading),
        }));
        const __VLS_83 = __VLS_82({
            ...{ 'onClick': {} },
            variant: "outlined",
            severity: "warn",
            disabled: (__VLS_ctx.loading),
        }, ...__VLS_functionalComponentArgsRest(__VLS_82));
        let __VLS_86;
        const __VLS_87 = ({ click: {} },
            { onClick: (__VLS_ctx.onForceDeleteClick) });
        const { default: __VLS_88 } = __VLS_84.slots;
        // @ts-ignore
        [isForceDelete, loading, onForceDeleteClick,];
        var __VLS_84;
        var __VLS_85;
    }
    else {
        let __VLS_89;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_90 = __VLS_asFunctionalComponent1(__VLS_89, new __VLS_89({
            ...{ 'onClick': {} },
            variant: "outlined",
            severity: "warn",
            disabled: (__VLS_ctx.loading),
        }));
        const __VLS_91 = __VLS_90({
            ...{ 'onClick': {} },
            variant: "outlined",
            severity: "warn",
            disabled: (__VLS_ctx.loading),
        }, ...__VLS_functionalComponentArgsRest(__VLS_90));
        let __VLS_94;
        const __VLS_95 = ({ click: {} },
            { onClick: (__VLS_ctx.onDeleteClick) });
        const { default: __VLS_96 } = __VLS_92.slots;
        // @ts-ignore
        [loading, onDeleteClick,];
        var __VLS_92;
        var __VLS_93;
    }
    let __VLS_97;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_98 = __VLS_asFunctionalComponent1(__VLS_97, new __VLS_97({
        type: "submit",
        loading: (__VLS_ctx.loading),
        form: "createDeploymentForm",
    }));
    const __VLS_99 = __VLS_98({
        type: "submit",
        loading: (__VLS_ctx.loading),
        form: "createDeploymentForm",
    }, ...__VLS_functionalComponentArgsRest(__VLS_98));
    const { default: __VLS_102 } = __VLS_100.slots;
    // @ts-ignore
    [loading,];
    var __VLS_100;
    // @ts-ignore
    [];
}
if (__VLS_ctx.isDeleting) {
    const __VLS_103 = DeploymentsDelete || DeploymentsDelete;
    // @ts-ignore
    const __VLS_104 = __VLS_asFunctionalComponent1(__VLS_103, new __VLS_103({
        ...{ 'onUpdate:visible': {} },
        ...{ 'onDelete': {} },
        visible: (__VLS_ctx.isDeleting),
        deploymentId: (__VLS_ctx.data.id),
        organizationId: (__VLS_ctx.collectionsStore.requestInfo.organizationId),
        orbitId: (__VLS_ctx.collectionsStore.requestInfo.orbitId),
        name: (__VLS_ctx.data.name),
    }));
    const __VLS_105 = __VLS_104({
        ...{ 'onUpdate:visible': {} },
        ...{ 'onDelete': {} },
        visible: (__VLS_ctx.isDeleting),
        deploymentId: (__VLS_ctx.data.id),
        organizationId: (__VLS_ctx.collectionsStore.requestInfo.organizationId),
        orbitId: (__VLS_ctx.collectionsStore.requestInfo.orbitId),
        name: (__VLS_ctx.data.name),
    }, ...__VLS_functionalComponentArgsRest(__VLS_104));
    let __VLS_108;
    const __VLS_109 = ({ 'update:visible': {} },
        { 'onUpdate:visible': (...[$event]) => {
                if (!(__VLS_ctx.isDeleting))
                    return;
                __VLS_ctx.isDeleting = false;
                // @ts-ignore
                [isDeleting, isDeleting, isDeleting, data, data, collectionsStore, collectionsStore,];
            } });
    const __VLS_110 = ({ delete: {} },
        { onDelete: (__VLS_ctx.onDelete) });
    var __VLS_106;
    var __VLS_107;
}
if (__VLS_ctx.isForceDeleting) {
    const __VLS_111 = ForceDeleteConfirmDialog || ForceDeleteConfirmDialog;
    // @ts-ignore
    const __VLS_112 = __VLS_asFunctionalComponent1(__VLS_111, new __VLS_111({
        ...{ 'onConfirm': {} },
        visible: (__VLS_ctx.isForceDeleting),
        title: "Force delete this deployment?",
        text: (__VLS_ctx.FORCE_DELETE_TEXT),
        loading: (__VLS_ctx.loading),
    }));
    const __VLS_113 = __VLS_112({
        ...{ 'onConfirm': {} },
        visible: (__VLS_ctx.isForceDeleting),
        title: "Force delete this deployment?",
        text: (__VLS_ctx.FORCE_DELETE_TEXT),
        loading: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_112));
    let __VLS_116;
    const __VLS_117 = ({ confirm: {} },
        { onConfirm: (__VLS_ctx.onForceDelete) });
    var __VLS_114;
    var __VLS_115;
}
// @ts-ignore
[loading, onDelete, isForceDeleting, isForceDeleting, FORCE_DELETE_TEXT, onForceDelete,];
var __VLS_3;
// @ts-ignore
var __VLS_21 = __VLS_20;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
