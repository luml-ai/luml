/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useRoute } from 'vue-router';
import { computed, onBeforeMount, ref, watch } from 'vue';
import { artifactCreateResolver } from '@/utils/forms/resolvers';
import { Form } from '@primevue/forms';
import { Dialog, Button, InputText, Textarea, AutoComplete, useToast, ProgressBar, Select, } from 'primevue';
import { useArtifactUpload } from '@/hooks/useArtifactUpload';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { useArtifactsTags } from '@/hooks/useArtifactsTags';
import { getErrorMessage } from '@/helpers/helpers';
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces';
import { isCorrectFileName, isDatasetFile, isExperimentFile, isModelFile } from '@/helpers/files';
import { useCollectionsStore } from '@/stores/collections';
import { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces';
import FileInput from '@/components/ui/FileInput.vue';
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
const makeInitialFormData = () => ({
    name: '',
    type: ArtifactTypeEnum.model,
    description: '',
    file: null,
    tags: [],
});
const initialFormData = makeInitialFormData();
const ARTIFACT_TYPE_OPTIONS = [
    { label: 'Model', value: ArtifactTypeEnum.model, disabled: false },
    { label: 'Dataset', value: ArtifactTypeEnum.dataset, disabled: false },
    { label: 'Experiment', value: ArtifactTypeEnum.experiment, disabled: false },
];
const { upload, progress } = useArtifactUpload();
const { getTagsByQuery, loadTags } = useArtifactsTags();
const toast = useToast();
const route = useRoute();
const collectionsStore = useCollectionsStore();
const visible = defineModel('visible');
const loading = ref(false);
const formData = ref(initialFormData);
const fileError = ref(false);
const autocompleteItems = ref([]);
const availableArtifactTypes = computed(() => {
    const collectionType = collectionsStore.currentCollection?.type;
    if (collectionType === OrbitCollectionTypeEnum.model) {
        return ARTIFACT_TYPE_OPTIONS.filter((type) => type.value === ArtifactTypeEnum.model);
    }
    else if (collectionType === OrbitCollectionTypeEnum.dataset) {
        return ARTIFACT_TYPE_OPTIONS.filter((type) => type.value === ArtifactTypeEnum.dataset);
    }
    else if (collectionType === OrbitCollectionTypeEnum.experiment) {
        return ARTIFACT_TYPE_OPTIONS.filter((type) => type.value === ArtifactTypeEnum.experiment);
    }
    else if (collectionType === OrbitCollectionTypeEnum.mixed) {
        return ARTIFACT_TYPE_OPTIONS;
    }
    return ARTIFACT_TYPE_OPTIONS;
});
const fileInfo = computed(() => {
    const file = formData.value.file;
    if (!file)
        return {};
    return {
        name: file.name,
        size: file.size,
    };
});
const fileInputAcceptText = computed(() => {
    if (formData.value.type === ArtifactTypeEnum.model) {
        return 'Accepts .luml, .dfs, .fnnx, .pyfnx file type';
    }
    else if (formData.value.type === ArtifactTypeEnum.experiment) {
        return 'Accepts .luml file type';
    }
    else if (formData.value.type === ArtifactTypeEnum.dataset) {
        return 'Accepts .tar file type';
    }
    else
        return '';
});
function searchTags(event) {
    autocompleteItems.value = getTagsByQuery(event.query);
}
function checkFileSize(size) {
    return size < 524288000;
}
function onSelectFile(event) {
    fileError.value = false;
    const isFileNameCorrect = isCorrectFileName(event.name);
    const isCorrectFileFormat = checkFileFormat(event.name);
    const fileSizeCorrect = checkFileSize(event.size);
    if (isCorrectFileFormat && isFileNameCorrect && fileSizeCorrect) {
        formData.value.file = event;
    }
    else {
        fileError.value = true;
        !isFileNameCorrect && toast.add(simpleErrorToast('Incorrect file name'));
    }
}
function checkFileFormat(fileName) {
    if (formData.value.type === ArtifactTypeEnum.model) {
        return isModelFile(fileName);
    }
    else if (formData.value.type === ArtifactTypeEnum.experiment) {
        return isExperimentFile(fileName);
    }
    else if (formData.value.type === ArtifactTypeEnum.dataset) {
        return isDatasetFile(fileName);
    }
    return false;
}
function onRemoveFile() {
    fileError.value = false;
    formData.value.file = null;
}
function getInitialArtifactType() {
    const collectionType = collectionsStore.currentCollection?.type;
    if (collectionType === OrbitCollectionTypeEnum.model) {
        return ArtifactTypeEnum.model;
    }
    else if (collectionType === OrbitCollectionTypeEnum.dataset) {
        return ArtifactTypeEnum.dataset;
    }
    else if (collectionType === OrbitCollectionTypeEnum.experiment) {
        return ArtifactTypeEnum.experiment;
    }
    return ArtifactTypeEnum.model;
}
async function onSubmit({ valid }) {
    if (!valid || !formData.value.file)
        return;
    loading.value = true;
    try {
        await upload(formData.value.file, formData.value.name, formData.value.type, formData.value.description, formData.value.tags);
        toast.add({
            severity: 'success',
            summary: 'Success',
            detail: `${formData.value.name} has been added to the collection successfully.<br><a href="#" class="toast-action-link" data-route="orbit-registry" data-params="{}">Go to Registry</a>`,
            life: 5000,
        });
        reset();
        visible.value = false;
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e?.message || 'Failed file upload'));
    }
    finally {
        loading.value = false;
    }
}
function reset() {
    formData.value = initialFormData;
    resetFile();
}
function resetFile() {
    formData.value.file = null;
    fileError.value = false;
}
async function initTags() {
    try {
        loadTags(String(route.params.organizationId), String(route.params.id), String(route.params.collectionId));
    }
    catch (e) {
        const message = getErrorMessage(e, 'Failed to load tags');
        toast.add(simpleErrorToast(message));
    }
}
onBeforeMount(() => {
    formData.value.type = getInitialArtifactType();
});
watch(visible, (val) => {
    val ? initTags() : reset();
});
watch(() => formData.value.type, resetFile);
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
    header: "add a new artifact",
    modal: true,
    draggable: (false),
    pt: (__VLS_ctx.dialogPt),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    header: "add a new artifact",
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
    resolver: (__VLS_ctx.artifactCreateResolver),
}));
const __VLS_9 = __VLS_8({
    ...{ 'onSubmit': {} },
    initialValues: (__VLS_ctx.formData),
    resolver: (__VLS_ctx.artifactCreateResolver),
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
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    modelValue: (__VLS_ctx.formData.name),
    id: "name",
    name: "name",
    placeholder: "Name your artifact",
    fluid: true,
}));
const __VLS_17 = __VLS_16({
    modelValue: (__VLS_ctx.formData.name),
    id: "name",
    name: "name",
    placeholder: "Name your artifact",
    fluid: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "type",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    modelValue: (__VLS_ctx.formData.type),
    options: (__VLS_ctx.availableArtifactTypes),
    optionLabel: "label",
    optionValue: "value",
    optionDisabled: "disabled",
    placeholder: "Select artifact types",
    name: "type",
    id: "type",
}));
const __VLS_22 = __VLS_21({
    modelValue: (__VLS_ctx.formData.type),
    options: (__VLS_ctx.availableArtifactTypes),
    optionLabel: "label",
    optionValue: "value",
    optionDisabled: "disabled",
    placeholder: "Select artifact types",
    name: "type",
    id: "type",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "description",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_25;
/** @ts-ignore @type { | typeof __VLS_components.Textarea | typeof __VLS_components.Textarea} */
Textarea;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
    modelValue: (__VLS_ctx.formData.description),
    name: "description",
    id: "description",
    placeholder: "Describe your artifact",
    ...{ style: {} },
}));
const __VLS_27 = __VLS_26({
    modelValue: (__VLS_ctx.formData.description),
    name: "description",
    id: "description",
    placeholder: "Describe your artifact",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "tags",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_30;
/** @ts-ignore @type { | typeof __VLS_components.AutoComplete | typeof __VLS_components.AutoComplete} */
AutoComplete;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.formData.tags),
    id: "tags",
    name: "tags",
    placeholder: "Type to add tags",
    fluid: true,
    multiple: true,
    suggestions: (__VLS_ctx.autocompleteItems),
}));
const __VLS_32 = __VLS_31({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.formData.tags),
    id: "tags",
    name: "tags",
    placeholder: "Type to add tags",
    fluid: true,
    multiple: true,
    suggestions: (__VLS_ctx.autocompleteItems),
}, ...__VLS_functionalComponentArgsRest(__VLS_31));
let __VLS_35;
const __VLS_36 = ({ complete: {} },
    { onComplete: (__VLS_ctx.searchTags) });
var __VLS_33;
var __VLS_34;
const __VLS_37 = FileInput;
// @ts-ignore
const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
    ...{ 'onSelectFile': {} },
    ...{ 'onRemoveFile': {} },
    id: "artifact-file",
    file: (__VLS_ctx.fileInfo),
    error: (__VLS_ctx.fileError),
    acceptText: (__VLS_ctx.fileInputAcceptText),
    uploadText: "upload artifact file",
    ...{ class: "file-field" },
}));
const __VLS_39 = __VLS_38({
    ...{ 'onSelectFile': {} },
    ...{ 'onRemoveFile': {} },
    id: "artifact-file",
    file: (__VLS_ctx.fileInfo),
    error: (__VLS_ctx.fileError),
    acceptText: (__VLS_ctx.fileInputAcceptText),
    uploadText: "upload artifact file",
    ...{ class: "file-field" },
}, ...__VLS_functionalComponentArgsRest(__VLS_38));
let __VLS_42;
const __VLS_43 = ({ selectFile: {} },
    { onSelectFile: (__VLS_ctx.onSelectFile) });
const __VLS_44 = ({ removeFile: {} },
    { onRemoveFile: (__VLS_ctx.onRemoveFile) });
/** @type {__VLS_StyleScopedClasses['file-field']} */ ;
var __VLS_40;
var __VLS_41;
if (__VLS_ctx.progress !== null) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "upload-section" },
    });
    /** @type {__VLS_StyleScopedClasses['upload-section']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "upload-description" },
    });
    /** @type {__VLS_StyleScopedClasses['upload-description']} */ ;
    let __VLS_45;
    /** @ts-ignore @type { | typeof __VLS_components.ProgressBar} */
    ProgressBar;
    // @ts-ignore
    const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({
        value: (__VLS_ctx.progress),
        showValue: true,
    }));
    const __VLS_47 = __VLS_46({
        value: (__VLS_ctx.progress),
        showValue: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_46));
}
let __VLS_50;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_51 = __VLS_asFunctionalComponent1(__VLS_50, new __VLS_50({
    type: "submit",
    fluid: true,
    rounded: true,
    loading: (__VLS_ctx.loading),
}));
const __VLS_52 = __VLS_51({
    type: "submit",
    fluid: true,
    rounded: true,
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_51));
const { default: __VLS_55 } = __VLS_53.slots;
// @ts-ignore
[visible, dialogPt, formData, formData, formData, formData, formData, artifactCreateResolver, onSubmit, availableArtifactTypes, autocompleteItems, searchTags, fileInfo, fileError, fileInputAcceptText, onSelectFile, onRemoveFile, progress, progress, loading,];
var __VLS_53;
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
