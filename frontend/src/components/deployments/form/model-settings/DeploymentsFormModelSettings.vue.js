/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { getErrorMessage } from '@/helpers/helpers';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { useCollectionsStore } from '@/stores/collections';
import { useArtifactsStore } from '@/stores/artifacts';
import { useToast, Accordion, AccordionPanel, AccordionHeader, AccordionContent, InputText, Button, } from 'primevue';
import { onBeforeMount, ref, watch } from 'vue';
import { HelpCircle, ChevronDown, ChevronUp, Plus, BellRing, Trash2 } from 'lucide-vue-next';
import { useSecretsStore } from '@/stores/orbit-secrets';
import { FnnxService } from '@/lib/fnnx/FnnxService';
import { FormField } from '@primevue/forms';
import { useRoute } from 'vue-router';
import SecretsSelect from '../../form/SecretsSelect.vue';
import CollectionSelect from './CollectionSelect.vue';
import ModelSelect from './ModelSelect.vue';
const props = defineProps();
const emit = defineEmits();
const collectionsStore = useCollectionsStore();
const artifactsStore = useArtifactsStore();
const secretsStore = useSecretsStore();
const toast = useToast();
const route = useRoute();
const secretsAccordion = ref([]);
const envAccordion = ref([]);
const collectionId = defineModel('collectionId');
const modelId = defineModel('modelId');
const secretDynamicAttributes = defineModel('secretDynamicAttributes', {
    default: [],
});
const secretEnvs = defineModel('secretEnvs', {
    default: [],
});
const dynamicAttributes = defineModel('dynamicAttributes', {
    default: [],
});
const notSecretEnvs = defineModel('notSecretEnvs', {
    default: [],
});
const customVariables = defineModel('customVariables', {
    default: [],
});
const selectedModel = ref(null);
async function getSecrets() {
    try {
        const { organizationId, orbitId } = collectionsStore.requestInfo;
        await secretsStore.loadSecrets(organizationId, orbitId);
    }
    catch (e) {
        toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load secrets')));
    }
}
function addCustomVariable() {
    customVariables.value?.push({ key: '', value: '' });
}
async function onModelIdChange(modelId) {
    try {
        if (modelId) {
            if (!collectionId.value)
                throw new Error('Collection ID is required');
            const requestInfo = {
                organizationId: String(route.params.organizationId),
                orbitId: String(route.params.id),
                collectionId: collectionId.value,
            };
            const model = await artifactsStore.getArtifact(modelId, requestInfo);
            selectedModel.value = model;
        }
        else {
            selectedModel.value = null;
        }
    }
    catch (e) {
        toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load model')));
    }
}
function onSelectedModelChange(model) {
    emit('modelChanged', model);
    customVariables.value = [];
    if (model) {
        setDynamicAttributes(model.manifest);
        setEnvs(model.manifest);
    }
    else {
        secretDynamicAttributes.value = [];
        dynamicAttributes.value = [];
        secretEnvs.value = [];
        notSecretEnvs.value = [];
    }
}
function getFieldFromVar(attributeData) {
    return {
        key: attributeData.name,
        label: attributeData.name,
        value: null,
    };
}
function setDynamicAttributes(manifest) {
    const { secrets, notSecrets } = FnnxService.getDynamicAttributes(manifest);
    secretDynamicAttributes.value = secrets.map(getFieldFromVar);
    dynamicAttributes.value = notSecrets.map(getFieldFromVar);
}
function setEnvs(manifest) {
    const { secrets, notSecrets } = FnnxService.getEnvVars(manifest);
    secretEnvs.value = secrets.map(getFieldFromVar);
    notSecretEnvs.value = notSecrets.map(getFieldFromVar);
}
function removeCustomVariable(removeIndex) {
    customVariables.value = customVariables.value.filter((item, index) => index !== removeIndex);
}
watch([secretEnvs, secretDynamicAttributes], ([envs, dynAttrs]) => {
    if (envs.length > 0 || dynAttrs.length > 0) {
        secretsAccordion.value = ['0'];
    }
}, { immediate: true, deep: true });
watch(notSecretEnvs, (envs) => {
    if (envs.length > 0) {
        envAccordion.value = ['0'];
    }
}, { immediate: true, deep: true });
watch(() => modelId.value, onModelIdChange, { immediate: true });
watch(selectedModel, onSelectedModelChange, { immediate: true });
onBeforeMount(async () => {
    await getSecrets();
    if (props.initialCollectionId) {
        collectionId.value = props.initialCollectionId;
    }
    if (props.initialModelId) {
        modelId.value = props.initialModelId;
    }
});
const __VLS_defaultModels = {
    'secretDynamicAttributes': [],
    'secretEnvs': [],
    'dynamicAttributes': [],
    'notSecretEnvs': [],
    'customVariables': [],
};
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
/** @type {__VLS_StyleScopedClasses['column']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "column" },
});
/** @type {__VLS_StyleScopedClasses['column']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
    ...{ class: "column-title" },
});
/** @type {__VLS_StyleScopedClasses['column-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "fields" },
});
/** @type {__VLS_StyleScopedClasses['fields']} */ ;
const __VLS_0 = CollectionSelect || CollectionSelect;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.collectionId),
    disabled: (!!__VLS_ctx.initialCollectionId),
    organizationId: (String(__VLS_ctx.$route.params.organizationId)),
    orbitId: (String(__VLS_ctx.$route.params.id)),
    initialCollectionId: (__VLS_ctx.initialCollectionId),
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.collectionId),
    disabled: (!!__VLS_ctx.initialCollectionId),
    organizationId: (String(__VLS_ctx.$route.params.organizationId)),
    orbitId: (String(__VLS_ctx.$route.params.id)),
    initialCollectionId: (__VLS_ctx.initialCollectionId),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const __VLS_5 = ModelSelect || ModelSelect;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    modelValue: (__VLS_ctx.modelId),
    disabled: (!!__VLS_ctx.initialModelId),
    organizationId: (String(__VLS_ctx.$route.params.organizationId)),
    orbitId: (String(__VLS_ctx.$route.params.id)),
    collectionId: (__VLS_ctx.collectionId || null),
    initialModelId: (__VLS_ctx.initialModelId),
}));
const __VLS_7 = __VLS_6({
    modelValue: (__VLS_ctx.modelId),
    disabled: (!!__VLS_ctx.initialModelId),
    organizationId: (String(__VLS_ctx.$route.params.organizationId)),
    orbitId: (String(__VLS_ctx.$route.params.id)),
    collectionId: (__VLS_ctx.collectionId || null),
    initialModelId: (__VLS_ctx.initialModelId),
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
if (__VLS_ctx.secretDynamicAttributes.length || __VLS_ctx.secretEnvs.length) {
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.Accordion | typeof __VLS_components.Accordion} */
    Accordion;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        multiple: (true),
        value: (__VLS_ctx.secretsAccordion),
        ...{ style: {} },
    }));
    const __VLS_12 = __VLS_11({
        multiple: (true),
        value: (__VLS_ctx.secretsAccordion),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    const { default: __VLS_15 } = __VLS_13.slots;
    {
        const { expandicon: __VLS_16 } = __VLS_13.slots;
        let __VLS_17;
        /** @ts-ignore @type { | typeof __VLS_components.ChevronDown | typeof __VLS_components.ChevronDown} */
        ChevronDown;
        // @ts-ignore
        const __VLS_18 = __VLS_asFunctionalComponent1(__VLS_17, new __VLS_17({
            size: (20),
        }));
        const __VLS_19 = __VLS_18({
            size: (20),
        }, ...__VLS_functionalComponentArgsRest(__VLS_18));
        // @ts-ignore
        [collectionId, collectionId, initialCollectionId, initialCollectionId, $route, $route, $route, $route, modelId, initialModelId, initialModelId, secretDynamicAttributes, secretEnvs, secretsAccordion,];
    }
    {
        const { collapseicon: __VLS_22 } = __VLS_13.slots;
        let __VLS_23;
        /** @ts-ignore @type { | typeof __VLS_components.ChevronUp | typeof __VLS_components.ChevronUp} */
        ChevronUp;
        // @ts-ignore
        const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
            size: (20),
        }));
        const __VLS_25 = __VLS_24({
            size: (20),
        }, ...__VLS_functionalComponentArgsRest(__VLS_24));
        // @ts-ignore
        [];
    }
    let __VLS_28;
    /** @ts-ignore @type { | typeof __VLS_components.AccordionPanel | typeof __VLS_components.AccordionPanel} */
    AccordionPanel;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
        value: "0",
    }));
    const __VLS_30 = __VLS_29({
        value: "0",
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    const { default: __VLS_33 } = __VLS_31.slots;
    let __VLS_34;
    /** @ts-ignore @type { | typeof __VLS_components.AccordionHeader | typeof __VLS_components.AccordionHeader} */
    AccordionHeader;
    // @ts-ignore
    const __VLS_35 = __VLS_asFunctionalComponent1(__VLS_34, new __VLS_34({}));
    const __VLS_36 = __VLS_35({}, ...__VLS_functionalComponentArgsRest(__VLS_35));
    const { default: __VLS_39 } = __VLS_37.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "accordion-title" },
    });
    /** @type {__VLS_StyleScopedClasses['accordion-title']} */ ;
    let __VLS_40;
    /** @ts-ignore @type { | typeof __VLS_components.HelpCircle | typeof __VLS_components.HelpCircle} */
    HelpCircle;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
        size: (12),
        color: "var(--p-button-text-secondary-color)",
    }));
    const __VLS_42 = __VLS_41({
        size: (12),
        color: "var(--p-button-text-secondary-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    // @ts-ignore
    [];
    var __VLS_37;
    let __VLS_45;
    /** @ts-ignore @type { | typeof __VLS_components.AccordionContent | typeof __VLS_components.AccordionContent} */
    AccordionContent;
    // @ts-ignore
    const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({}));
    const __VLS_47 = __VLS_46({}, ...__VLS_functionalComponentArgsRest(__VLS_46));
    const { default: __VLS_50 } = __VLS_48.slots;
    for (const [secret, index] of __VLS_vFor((__VLS_ctx.secretEnvs))) {
        let __VLS_51;
        /** @ts-ignore @type { | typeof __VLS_components.FormField | typeof __VLS_components.FormField} */
        FormField;
        // @ts-ignore
        const __VLS_52 = __VLS_asFunctionalComponent1(__VLS_51, new __VLS_51({
            key: (secret.key),
            name: (`secretEnvs.${index}.value`),
            ...{ class: "field" },
        }));
        const __VLS_53 = __VLS_52({
            key: (secret.key),
            name: (`secretEnvs.${index}.value`),
            ...{ class: "field" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_52));
        /** @type {__VLS_StyleScopedClasses['field']} */ ;
        const { default: __VLS_56 } = __VLS_54.slots;
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            ...{ class: "label" },
        });
        /** @type {__VLS_StyleScopedClasses['label']} */ ;
        (secret.label);
        const __VLS_57 = SecretsSelect || SecretsSelect;
        // @ts-ignore
        const __VLS_58 = __VLS_asFunctionalComponent1(__VLS_57, new __VLS_57({
            modelValue: (secret.value),
            secretsList: (__VLS_ctx.secretsStore.secretsList),
        }));
        const __VLS_59 = __VLS_58({
            modelValue: (secret.value),
            secretsList: (__VLS_ctx.secretsStore.secretsList),
        }, ...__VLS_functionalComponentArgsRest(__VLS_58));
        // @ts-ignore
        [secretEnvs, secretsStore,];
        var __VLS_54;
        // @ts-ignore
        [];
    }
    for (const [secret, index] of __VLS_vFor((__VLS_ctx.secretDynamicAttributes))) {
        let __VLS_62;
        /** @ts-ignore @type { | typeof __VLS_components.FormField | typeof __VLS_components.FormField} */
        FormField;
        // @ts-ignore
        const __VLS_63 = __VLS_asFunctionalComponent1(__VLS_62, new __VLS_62({
            key: (secret.key),
            name: (`secretDynamicAttributes.${index}.value`),
            ...{ class: "field" },
        }));
        const __VLS_64 = __VLS_63({
            key: (secret.key),
            name: (`secretDynamicAttributes.${index}.value`),
            ...{ class: "field" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_63));
        /** @type {__VLS_StyleScopedClasses['field']} */ ;
        const { default: __VLS_67 } = __VLS_65.slots;
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            ...{ class: "label" },
        });
        /** @type {__VLS_StyleScopedClasses['label']} */ ;
        (secret.label);
        const __VLS_68 = SecretsSelect || SecretsSelect;
        // @ts-ignore
        const __VLS_69 = __VLS_asFunctionalComponent1(__VLS_68, new __VLS_68({
            modelValue: (secret.value),
            secretsList: (__VLS_ctx.secretsStore.secretsList),
        }));
        const __VLS_70 = __VLS_69({
            modelValue: (secret.value),
            secretsList: (__VLS_ctx.secretsStore.secretsList),
        }, ...__VLS_functionalComponentArgsRest(__VLS_69));
        // @ts-ignore
        [secretDynamicAttributes, secretsStore,];
        var __VLS_65;
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_48;
    // @ts-ignore
    [];
    var __VLS_31;
    // @ts-ignore
    [];
    var __VLS_13;
}
if (__VLS_ctx.notSecretEnvs.length) {
    let __VLS_73;
    /** @ts-ignore @type { | typeof __VLS_components.Accordion | typeof __VLS_components.Accordion} */
    Accordion;
    // @ts-ignore
    const __VLS_74 = __VLS_asFunctionalComponent1(__VLS_73, new __VLS_73({
        value: (__VLS_ctx.envAccordion),
        multiple: (true),
    }));
    const __VLS_75 = __VLS_74({
        value: (__VLS_ctx.envAccordion),
        multiple: (true),
    }, ...__VLS_functionalComponentArgsRest(__VLS_74));
    const { default: __VLS_78 } = __VLS_76.slots;
    {
        const { expandicon: __VLS_79 } = __VLS_76.slots;
        let __VLS_80;
        /** @ts-ignore @type { | typeof __VLS_components.ChevronDown | typeof __VLS_components.ChevronDown} */
        ChevronDown;
        // @ts-ignore
        const __VLS_81 = __VLS_asFunctionalComponent1(__VLS_80, new __VLS_80({
            size: (20),
        }));
        const __VLS_82 = __VLS_81({
            size: (20),
        }, ...__VLS_functionalComponentArgsRest(__VLS_81));
        // @ts-ignore
        [notSecretEnvs, envAccordion,];
    }
    {
        const { collapseicon: __VLS_85 } = __VLS_76.slots;
        let __VLS_86;
        /** @ts-ignore @type { | typeof __VLS_components.ChevronUp | typeof __VLS_components.ChevronUp} */
        ChevronUp;
        // @ts-ignore
        const __VLS_87 = __VLS_asFunctionalComponent1(__VLS_86, new __VLS_86({
            size: (20),
        }));
        const __VLS_88 = __VLS_87({
            size: (20),
        }, ...__VLS_functionalComponentArgsRest(__VLS_87));
        // @ts-ignore
        [];
    }
    let __VLS_91;
    /** @ts-ignore @type { | typeof __VLS_components.AccordionPanel | typeof __VLS_components.AccordionPanel} */
    AccordionPanel;
    // @ts-ignore
    const __VLS_92 = __VLS_asFunctionalComponent1(__VLS_91, new __VLS_91({
        value: "0",
    }));
    const __VLS_93 = __VLS_92({
        value: "0",
    }, ...__VLS_functionalComponentArgsRest(__VLS_92));
    const { default: __VLS_96 } = __VLS_94.slots;
    let __VLS_97;
    /** @ts-ignore @type { | typeof __VLS_components.AccordionHeader | typeof __VLS_components.AccordionHeader} */
    AccordionHeader;
    // @ts-ignore
    const __VLS_98 = __VLS_asFunctionalComponent1(__VLS_97, new __VLS_97({}));
    const __VLS_99 = __VLS_98({}, ...__VLS_functionalComponentArgsRest(__VLS_98));
    const { default: __VLS_102 } = __VLS_100.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "accordion-title" },
    });
    /** @type {__VLS_StyleScopedClasses['accordion-title']} */ ;
    let __VLS_103;
    /** @ts-ignore @type { | typeof __VLS_components.HelpCircle | typeof __VLS_components.HelpCircle} */
    HelpCircle;
    // @ts-ignore
    const __VLS_104 = __VLS_asFunctionalComponent1(__VLS_103, new __VLS_103({
        size: (12),
        color: "var(--p-button-text-secondary-color)",
    }));
    const __VLS_105 = __VLS_104({
        size: (12),
        color: "var(--p-button-text-secondary-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_104));
    // @ts-ignore
    [];
    var __VLS_100;
    let __VLS_108;
    /** @ts-ignore @type { | typeof __VLS_components.AccordionContent | typeof __VLS_components.AccordionContent} */
    AccordionContent;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent1(__VLS_108, new __VLS_108({}));
    const __VLS_110 = __VLS_109({}, ...__VLS_functionalComponentArgsRest(__VLS_109));
    const { default: __VLS_113 } = __VLS_111.slots;
    for (const [variable, index] of __VLS_vFor((__VLS_ctx.notSecretEnvs))) {
        let __VLS_114;
        /** @ts-ignore @type { | typeof __VLS_components.FormField | typeof __VLS_components.FormField} */
        FormField;
        // @ts-ignore
        const __VLS_115 = __VLS_asFunctionalComponent1(__VLS_114, new __VLS_114({
            key: (variable.key),
            name: (`notSecretEnvs.${index}.value`),
            ...{ class: "field" },
        }));
        const __VLS_116 = __VLS_115({
            key: (variable.key),
            name: (`notSecretEnvs.${index}.value`),
            ...{ class: "field" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_115));
        /** @type {__VLS_StyleScopedClasses['field']} */ ;
        const { default: __VLS_119 } = __VLS_117.slots;
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            ...{ class: "label" },
        });
        /** @type {__VLS_StyleScopedClasses['label']} */ ;
        (variable.label);
        let __VLS_120;
        /** @ts-ignore @type { | typeof __VLS_components.InputText | typeof __VLS_components.InputText} */
        InputText;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent1(__VLS_120, new __VLS_120({
            modelValue: (variable.value),
            placeholder: "Enter value",
            size: "small",
        }));
        const __VLS_122 = __VLS_121({
            modelValue: (variable.value),
            placeholder: "Enter value",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        // @ts-ignore
        [notSecretEnvs,];
        var __VLS_117;
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_111;
    // @ts-ignore
    [];
    var __VLS_94;
    // @ts-ignore
    [];
    var __VLS_76;
}
let __VLS_125;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_126 = __VLS_asFunctionalComponent1(__VLS_125, new __VLS_125({
    ...{ 'onClick': {} },
    label: "Add custom variable",
    variant: "text",
    ...{ style: {} },
}));
const __VLS_127 = __VLS_126({
    ...{ 'onClick': {} },
    label: "Add custom variable",
    variant: "text",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_126));
let __VLS_130;
const __VLS_131 = ({ click: {} },
    { onClick: (__VLS_ctx.addCustomVariable) });
const { default: __VLS_132 } = __VLS_128.slots;
{
    const { icon: __VLS_133 } = __VLS_128.slots;
    let __VLS_134;
    /** @ts-ignore @type { | typeof __VLS_components.Plus} */
    Plus;
    // @ts-ignore
    const __VLS_135 = __VLS_asFunctionalComponent1(__VLS_134, new __VLS_134({
        size: (14),
    }));
    const __VLS_136 = __VLS_135({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_135));
    // @ts-ignore
    [addCustomVariable,];
}
// @ts-ignore
[];
var __VLS_128;
var __VLS_129;
if (__VLS_ctx.customVariables.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "custom-variables" },
    });
    /** @type {__VLS_StyleScopedClasses['custom-variables']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "accordion-title" },
    });
    /** @type {__VLS_StyleScopedClasses['accordion-title']} */ ;
    let __VLS_139;
    /** @ts-ignore @type { | typeof __VLS_components.HelpCircle | typeof __VLS_components.HelpCircle} */
    HelpCircle;
    // @ts-ignore
    const __VLS_140 = __VLS_asFunctionalComponent1(__VLS_139, new __VLS_139({
        size: (12),
        color: "var(--p-button-text-secondary-color)",
    }));
    const __VLS_141 = __VLS_140({
        size: (12),
        color: "var(--p-button-text-secondary-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_140));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "custom-variables__content" },
    });
    /** @type {__VLS_StyleScopedClasses['custom-variables__content']} */ ;
    for (const [item, index] of __VLS_vFor((__VLS_ctx.customVariables))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (index),
            ...{ class: "custom-variables__item" },
        });
        /** @type {__VLS_StyleScopedClasses['custom-variables__item']} */ ;
        let __VLS_144;
        /** @ts-ignore @type { | typeof __VLS_components.FormField | typeof __VLS_components.FormField} */
        FormField;
        // @ts-ignore
        const __VLS_145 = __VLS_asFunctionalComponent1(__VLS_144, new __VLS_144({
            name: (`customVariables.${index}.key`),
        }));
        const __VLS_146 = __VLS_145({
            name: (`customVariables.${index}.key`),
        }, ...__VLS_functionalComponentArgsRest(__VLS_145));
        const { default: __VLS_149 } = __VLS_147.slots;
        let __VLS_150;
        /** @ts-ignore @type { | typeof __VLS_components.InputText | typeof __VLS_components.InputText} */
        InputText;
        // @ts-ignore
        const __VLS_151 = __VLS_asFunctionalComponent1(__VLS_150, new __VLS_150({
            modelValue: (item.key),
            placeholder: "Enter key",
            size: "small",
            fluid: true,
        }));
        const __VLS_152 = __VLS_151({
            modelValue: (item.key),
            placeholder: "Enter key",
            size: "small",
            fluid: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_151));
        // @ts-ignore
        [customVariables, customVariables,];
        var __VLS_147;
        let __VLS_155;
        /** @ts-ignore @type { | typeof __VLS_components.FormField | typeof __VLS_components.FormField} */
        FormField;
        // @ts-ignore
        const __VLS_156 = __VLS_asFunctionalComponent1(__VLS_155, new __VLS_155({
            name: (`customVariables.${index}.value`),
        }));
        const __VLS_157 = __VLS_156({
            name: (`customVariables.${index}.value`),
        }, ...__VLS_functionalComponentArgsRest(__VLS_156));
        const { default: __VLS_160 } = __VLS_158.slots;
        let __VLS_161;
        /** @ts-ignore @type { | typeof __VLS_components.InputText | typeof __VLS_components.InputText} */
        InputText;
        // @ts-ignore
        const __VLS_162 = __VLS_asFunctionalComponent1(__VLS_161, new __VLS_161({
            modelValue: (item.value),
            placeholder: "Enter value",
            size: "small",
            fluid: true,
        }));
        const __VLS_163 = __VLS_162({
            modelValue: (item.value),
            placeholder: "Enter value",
            size: "small",
            fluid: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_162));
        // @ts-ignore
        [];
        var __VLS_158;
        let __VLS_166;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_167 = __VLS_asFunctionalComponent1(__VLS_166, new __VLS_166({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "text",
            size: "small",
        }));
        const __VLS_168 = __VLS_167({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "text",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_167));
        let __VLS_171;
        const __VLS_172 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.customVariables.length))
                        return;
                    __VLS_ctx.removeCustomVariable(index);
                    // @ts-ignore
                    [removeCustomVariable,];
                } });
        const { default: __VLS_173 } = __VLS_169.slots;
        {
            const { icon: __VLS_174 } = __VLS_169.slots;
            let __VLS_175;
            /** @ts-ignore @type { | typeof __VLS_components.Trash2 | typeof __VLS_components.Trash2} */
            Trash2;
            // @ts-ignore
            const __VLS_176 = __VLS_asFunctionalComponent1(__VLS_175, new __VLS_175({
                size: (14),
            }));
            const __VLS_177 = __VLS_176({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_176));
            // @ts-ignore
            [];
        }
        // @ts-ignore
        [];
        var __VLS_169;
        var __VLS_170;
        // @ts-ignore
        [];
    }
}
if (__VLS_ctx.dynamicAttributes?.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "dynamic-attributes" },
    });
    /** @type {__VLS_StyleScopedClasses['dynamic-attributes']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "dynamic-attributes-message" },
    });
    /** @type {__VLS_StyleScopedClasses['dynamic-attributes-message']} */ ;
    let __VLS_180;
    /** @ts-ignore @type { | typeof __VLS_components.BellRing | typeof __VLS_components.BellRing} */
    BellRing;
    // @ts-ignore
    const __VLS_181 = __VLS_asFunctionalComponent1(__VLS_180, new __VLS_180({
        size: (14),
        ...{ class: "dynamic-attributes-icon" },
    }));
    const __VLS_182 = __VLS_181({
        size: (14),
        ...{ class: "dynamic-attributes-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_181));
    /** @type {__VLS_StyleScopedClasses['dynamic-attributes-icon']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.br)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "dynamic-attributes-tags" },
    });
    /** @type {__VLS_StyleScopedClasses['dynamic-attributes-tags']} */ ;
    for (const [attribute] of __VLS_vFor((__VLS_ctx.dynamicAttributes))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (attribute.key),
            ...{ class: "dynamic-attributes-tag" },
        });
        /** @type {__VLS_StyleScopedClasses['dynamic-attributes-tag']} */ ;
        (attribute.label);
        // @ts-ignore
        [dynamicAttributes, dynamicAttributes,];
    }
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
