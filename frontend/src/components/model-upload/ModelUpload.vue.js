/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, onBeforeMount, ref, watch } from 'vue';
import { Form } from '@primevue/forms';
import { Button, Select, Dialog, InputText, Textarea, AutoComplete, useToast } from 'primevue';
import { useOrbitsStore } from '@/stores/orbits';
import { useOrganizationStore } from '@/stores/organization';
import { useArtifactsTags } from '@/hooks/useArtifactsTags';
import { useArtifactUpload } from '@/hooks/useArtifactUpload';
import { modelUploadResolver } from '@/utils/forms/resolvers';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces';
import ArtifactUploadCollectionSelect from './ModelUploadCollectionSelect.vue';
const props = defineProps();
const dialogPt = {
    root: {
        style: 'max-width: 500px; width: 100%;',
    },
    header: {
        style: 'padding: 28px; text-transform: uppercase; font-size: 20px;',
    },
    content: {
        style: 'padding: 0 28px 28px;',
    },
};
const visible = defineModel('visible');
const organizationStore = useOrganizationStore();
const orbitsStore = useOrbitsStore();
const toast = useToast();
const { getTagsByQuery, loadTags } = useArtifactsTags();
const { upload } = useArtifactUpload();
const loading = ref(false);
const formData = ref({
    orbit: null,
    collection: null,
    name: '',
    description: '',
    tags: [],
});
const autocompleteItems = ref([]);
const organizationId = computed(() => {
    if (!organizationStore.currentOrganization?.id)
        throw new Error('Current organization not found');
    return organizationStore.currentOrganization.id;
});
async function getOrbitsList() {
    await orbitsStore.loadOrbitsList(organizationId.value);
}
function searchTags(event) {
    autocompleteItems.value = getTagsByQuery(event.query);
}
async function onCollectionChange(collectionId) {
    if (collectionId) {
        if (!formData.value.orbit)
            throw new Error('Orbit was not found');
        await loadTags(organizationId.value, formData.value.orbit, collectionId);
    }
}
function getRequestInfo() {
    if (!formData.value.orbit)
        throw new Error('Orbit was not found');
    if (!formData.value.collection)
        throw new Error('Collection not found');
    return {
        organizationId: organizationId.value,
        orbitId: formData.value.orbit,
        collectionId: formData.value.collection,
    };
}
async function onSubmit({ valid }) {
    if (!valid)
        return;
    try {
        loading.value = true;
        const timestamp = Date.now();
        const filename = props.fileName ? props.fileName : `${props.currentTask}_${timestamp}.luml`;
        const file = new File([props.modelBlob], filename);
        const ids = getRequestInfo();
        await upload(file, formData.value.name, ArtifactTypeEnum.model, formData.value.description, [...formData.value.tags], ids);
        toast.add(simpleSuccessToast(`${formData.value.name} has been added to the collection successfully.`));
        visible.value = false;
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e?.message || 'Failed file upload'));
    }
    finally {
        loading.value = false;
    }
}
onBeforeMount(async () => {
    await getOrbitsList();
});
watch(() => formData.value.collection, onCollectionChange);
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
    header: "upload model to registry",
    modal: true,
    draggable: (false),
    pt: (__VLS_ctx.dialogPt),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    header: "upload model to registry",
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
    resolver: (__VLS_ctx.modelUploadResolver),
}));
const __VLS_9 = __VLS_8({
    ...{ 'onSubmit': {} },
    initialValues: (__VLS_ctx.formData),
    resolver: (__VLS_ctx.modelUploadResolver),
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
let __VLS_12;
const __VLS_13 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onSubmit) });
const { default: __VLS_14 } = __VLS_10.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "inputs" },
});
/** @type {__VLS_StyleScopedClasses['inputs']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "name",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_15;
/** @ts-ignore @type { | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    modelValue: (__VLS_ctx.formData.orbit),
    id: "orbit",
    name: "orbit",
    placeholder: "Select orbit",
    fluid: true,
    options: (__VLS_ctx.orbitsStore.orbitsList),
    optionLabel: "name",
    optionValue: "id",
}));
const __VLS_17 = __VLS_16({
    modelValue: (__VLS_ctx.formData.orbit),
    id: "orbit",
    name: "orbit",
    placeholder: "Select orbit",
    fluid: true,
    options: (__VLS_ctx.orbitsStore.orbitsList),
    optionLabel: "name",
    optionValue: "id",
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
const __VLS_20 = ArtifactUploadCollectionSelect;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    modelValue: (__VLS_ctx.formData.collection),
    organizationId: (__VLS_ctx.organizationId),
    orbitId: (__VLS_ctx.formData.orbit),
}));
const __VLS_22 = __VLS_21({
    modelValue: (__VLS_ctx.formData.collection),
    organizationId: (__VLS_ctx.organizationId),
    orbitId: (__VLS_ctx.formData.orbit),
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "name",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_25;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
    modelValue: (__VLS_ctx.formData.name),
    id: "name",
    name: "name",
    placeholder: "Name your artifact",
    fluid: true,
}));
const __VLS_27 = __VLS_26({
    modelValue: (__VLS_ctx.formData.name),
    id: "name",
    name: "name",
    placeholder: "Name your artifact",
    fluid: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "description",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_30;
/** @ts-ignore @type { | typeof __VLS_components.Textarea | typeof __VLS_components.Textarea} */
Textarea;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
    modelValue: (__VLS_ctx.formData.description),
    name: "description",
    id: "description",
    placeholder: "Describe your artifact",
    ...{ style: {} },
}));
const __VLS_32 = __VLS_31({
    modelValue: (__VLS_ctx.formData.description),
    name: "description",
    id: "description",
    placeholder: "Describe your artifact",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_31));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "tags",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_35;
/** @ts-ignore @type { | typeof __VLS_components.AutoComplete | typeof __VLS_components.AutoComplete} */
AutoComplete;
// @ts-ignore
const __VLS_36 = __VLS_asFunctionalComponent1(__VLS_35, new __VLS_35({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.formData.tags),
    id: "tags",
    name: "tags",
    placeholder: "Type to add tags",
    fluid: true,
    multiple: true,
    suggestions: (__VLS_ctx.autocompleteItems),
}));
const __VLS_37 = __VLS_36({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.formData.tags),
    id: "tags",
    name: "tags",
    placeholder: "Type to add tags",
    fluid: true,
    multiple: true,
    suggestions: (__VLS_ctx.autocompleteItems),
}, ...__VLS_functionalComponentArgsRest(__VLS_36));
let __VLS_40;
const __VLS_41 = ({ complete: {} },
    { onComplete: (__VLS_ctx.searchTags) });
var __VLS_38;
var __VLS_39;
let __VLS_42;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_43 = __VLS_asFunctionalComponent1(__VLS_42, new __VLS_42({
    type: "submit",
    fluid: true,
    rounded: true,
    loading: (__VLS_ctx.loading),
}));
const __VLS_44 = __VLS_43({
    type: "submit",
    fluid: true,
    rounded: true,
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_43));
const { default: __VLS_47 } = __VLS_45.slots;
// @ts-ignore
[visible, dialogPt, formData, formData, formData, formData, formData, formData, formData, modelUploadResolver, onSubmit, orbitsStore, organizationId, autocompleteItems, searchTags, loading,];
var __VLS_45;
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
