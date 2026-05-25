/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { PermissionEnum } from '@/lib/api/api.interfaces';
import { useOrbitsStore } from '@/stores/orbits';
import { Bolt, Download, Repeat, Rocket, Trash2 } from 'lucide-vue-next';
import { computed, ref } from 'vue';
import { ArtifactStatusEnum, ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces';
import { FnnxService } from '@/lib/fnnx/FnnxService';
import { useArtifactsStore } from '@/stores/artifacts';
import { Button, useConfirm, useToast } from 'primevue';
import { useRouter } from 'vue-router';
import { deleteArtifactConfirmOptions } from '@/lib/primevue/data/confirm';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { useCollectionsStore } from '@/stores/collections';
import { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces';
import ArtifactEditor from '../artifact/ArtifactEditor.vue';
import ForceDeleteConfirmDialog from '@/components/ui/dialogs/ForceDeleteConfirmDialog.vue';
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue';
import MetricsSelect from './MetricsSelect.vue';
const FORCE_DELETE_TEXT = 'This action will permanently delete the models. If your bucket still contains the model files, the storage space will not be freed until you remove them manually. <br /> If you are sure, then write "delete" below';
const orbitsStore = useOrbitsStore();
const collectionsStore = useCollectionsStore();
const artifactsStore = useArtifactsStore();
const router = useRouter();
const confirm = useConfirm();
const toast = useToast();
const props = defineProps();
const emits = defineEmits();
const selectedMetrics = defineModel('selectedMetrics');
const loading = ref(false);
const isForceDeleting = ref(false);
const modelForEdit = ref(null);
const modelForDeployment = ref(null);
const downloadButtonDisabled = computed(() => !props.selectedArtifacts.length);
const compareButtonDisabled = computed(() => {
    if (props.selectedArtifacts.length < 2)
        return true;
    const hasInvalidStatus = props.selectedArtifacts.some((artifact) => artifact.status !== ArtifactStatusEnum.uploaded);
    if (hasInvalidStatus)
        return true;
    const hasAllExperimentSnapshots = props.selectedArtifacts.every((selectedArtifact) => {
        const archiveName = FnnxService.findExperimentSnapshotArchiveName(selectedArtifact.file_index);
        return !!archiveName;
    });
    return !hasAllExperimentSnapshots;
});
const forceDeleteTitle = computed(() => {
    return props.selectedArtifacts.length > 1
        ? 'Force delete these artifacts?'
        : 'Force delete this artifact?';
});
const deployButtonDisabled = computed(() => {
    if (props.selectedArtifacts.length !== 1)
        return true;
    const artifact = props.selectedArtifacts[0];
    const isUploaded = artifact.status === ArtifactStatusEnum.uploaded;
    if (!isUploaded)
        return true;
    const isModel = artifact.type === ArtifactTypeEnum.model;
    if (isModel)
        return false;
    return true;
});
const showDeployButton = computed(() => {
    return (collectionsStore.currentCollection?.type === OrbitCollectionTypeEnum.model ||
        collectionsStore.currentCollection?.type === OrbitCollectionTypeEnum.mixed);
});
const showCompareButton = computed(() => {
    return collectionsStore.currentCollection?.type !== OrbitCollectionTypeEnum.dataset;
});
async function onDeleteClick() {
    if (!props.selectedArtifacts.length || loading.value)
        return;
    const hasFailedStatus = props.selectedArtifacts.some((artifact) => artifact.status !== ArtifactStatusEnum.uploaded);
    if (hasFailedStatus) {
        isForceDeleting.value = true;
    }
    else {
        confirm.require(deleteArtifactConfirmOptions(confirmDelete, props.selectedArtifacts.length));
    }
}
async function confirmDelete() {
    try {
        const artifactsForDelete = props.selectedArtifacts.map((artifact) => artifact.id) || [];
        loading.value = true;
        const result = await artifactsStore.deleteArtifacts(artifactsForDelete);
        if (result.deleted?.length) {
            showSuccessDeleteToast(result.deleted);
        }
        if (result.failed?.length) {
            showErrorDeleteToast(result.failed);
        }
    }
    catch {
        toast.add(simpleErrorToast('Failed to delete artifacts'));
    }
    finally {
        emits('clearSelectedArtifacts');
        loading.value = false;
    }
}
async function onForceDelete() {
    try {
        const artifactsForDelete = props.selectedArtifacts.map((artifact) => artifact.id) || [];
        loading.value = true;
        const result = await artifactsStore.forceDeleteArtifacts(artifactsForDelete);
        if (result.deleted?.length) {
            showSuccessDeleteToast(result.deleted);
        }
        if (result.failed?.length) {
            showErrorDeleteToast(result.failed);
        }
    }
    catch {
        toast.add(simpleErrorToast('Failed to delete artifacts'));
    }
    finally {
        emits('clearSelectedArtifacts');
        loading.value = false;
        isForceDeleting.value = false;
    }
}
function showSuccessDeleteToast(artifacts) {
    toast.add(simpleSuccessToast(`Artifacts: ${artifacts} has been removed from the collection successfully`));
}
function showErrorDeleteToast(artifacts) {
    toast.add(simpleErrorToast(`Failed to delete the artifacts: ${artifacts}`));
}
function openModelEditor() {
    if (!props.selectedArtifacts.length)
        return;
    modelForEdit.value = props.selectedArtifacts[0];
}
function compareClick() {
    if (!props.selectedArtifacts.length)
        return;
    const selectedArtifactsIds = props.selectedArtifacts.map((artifact) => artifact.id);
    router.push({ name: 'compare', query: { artifacts: selectedArtifactsIds } });
}
async function downloadClick() {
    if (!props.selectedArtifacts.length)
        throw new Error('Select artifact before');
    if (!props.selectedArtifacts[0]?.id || loading.value)
        return;
    loading.value = true;
    try {
        const artifact = props.selectedArtifacts[0];
        await artifactsStore.downloadArtifact(artifact.id, artifact.file_name);
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to load artifacts'));
    }
    finally {
        emits('clearSelectedArtifacts');
        loading.value = false;
    }
}
function onDeployClick() {
    const modelId = props.selectedArtifacts[0].id;
    modelForDeployment.value = modelId;
}
function onUpdateModelDeploymentVisible(val) {
    if (val)
        return;
    modelForDeployment.value = null;
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar" },
});
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar-left" },
});
/** @type {__VLS_StyleScopedClasses['toolbar-left']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "counter" },
});
/** @type {__VLS_StyleScopedClasses['counter']} */ ;
(__VLS_ctx.selectedArtifacts.length);
if (__VLS_ctx.orbitsStore.getCurrentOrbitPermissions?.artifact.includes(__VLS_ctx.PermissionEnum.delete)) {
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
        disabled: (!__VLS_ctx.selectedArtifacts.length),
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
        disabled: (!__VLS_ctx.selectedArtifacts.length),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ click: {} },
        { onClick: (__VLS_ctx.onDeleteClick) });
    __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, value: ('Delete') }, null, null);
    const { default: __VLS_7 } = __VLS_3.slots;
    {
        const { icon: __VLS_8 } = __VLS_3.slots;
        let __VLS_9;
        /** @ts-ignore @type { | typeof __VLS_components.Trash2} */
        Trash2;
        // @ts-ignore
        const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
            size: (14),
        }));
        const __VLS_11 = __VLS_10({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_10));
        // @ts-ignore
        [selectedArtifacts, selectedArtifacts, orbitsStore, PermissionEnum, onDeleteClick, vTooltip,];
    }
    // @ts-ignore
    [];
    var __VLS_3;
    var __VLS_4;
}
if (__VLS_ctx.orbitsStore.getCurrentOrbitPermissions?.artifact.includes(__VLS_ctx.PermissionEnum.update)) {
    let __VLS_14;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
        disabled: (__VLS_ctx.selectedArtifacts.length !== 1),
    }));
    const __VLS_16 = __VLS_15({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
        disabled: (__VLS_ctx.selectedArtifacts.length !== 1),
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    let __VLS_19;
    const __VLS_20 = ({ click: {} },
        { onClick: (__VLS_ctx.openModelEditor) });
    __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, value: ('Settings') }, null, null);
    const { default: __VLS_21 } = __VLS_17.slots;
    {
        const { icon: __VLS_22 } = __VLS_17.slots;
        let __VLS_23;
        /** @ts-ignore @type { | typeof __VLS_components.Bolt} */
        Bolt;
        // @ts-ignore
        const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
            size: (14),
        }));
        const __VLS_25 = __VLS_24({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_24));
        // @ts-ignore
        [selectedArtifacts, orbitsStore, PermissionEnum, vTooltip, openModelEditor,];
    }
    // @ts-ignore
    [];
    var __VLS_17;
    var __VLS_18;
}
let __VLS_28;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
    disabled: (__VLS_ctx.downloadButtonDisabled),
}));
const __VLS_30 = __VLS_29({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
    disabled: (__VLS_ctx.downloadButtonDisabled),
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
let __VLS_33;
const __VLS_34 = ({ click: {} },
    { onClick: (__VLS_ctx.downloadClick) });
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, value: ('Download') }, null, null);
const { default: __VLS_35 } = __VLS_31.slots;
{
    const { icon: __VLS_36 } = __VLS_31.slots;
    let __VLS_37;
    /** @ts-ignore @type { | typeof __VLS_components.Download} */
    Download;
    // @ts-ignore
    const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
        size: (14),
    }));
    const __VLS_39 = __VLS_38({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_38));
    // @ts-ignore
    [vTooltip, downloadButtonDisabled, downloadClick,];
}
// @ts-ignore
[];
var __VLS_31;
var __VLS_32;
if (__VLS_ctx.showDeployButton) {
    let __VLS_42;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_43 = __VLS_asFunctionalComponent1(__VLS_42, new __VLS_42({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
        disabled: (__VLS_ctx.deployButtonDisabled),
    }));
    const __VLS_44 = __VLS_43({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
        disabled: (__VLS_ctx.deployButtonDisabled),
    }, ...__VLS_functionalComponentArgsRest(__VLS_43));
    let __VLS_47;
    const __VLS_48 = ({ click: {} },
        { onClick: (__VLS_ctx.onDeployClick) });
    __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, value: ('Deploy') }, null, null);
    const { default: __VLS_49 } = __VLS_45.slots;
    {
        const { icon: __VLS_50 } = __VLS_45.slots;
        let __VLS_51;
        /** @ts-ignore @type { | typeof __VLS_components.Rocket} */
        Rocket;
        // @ts-ignore
        const __VLS_52 = __VLS_asFunctionalComponent1(__VLS_51, new __VLS_51({
            size: (14),
        }));
        const __VLS_53 = __VLS_52({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_52));
        // @ts-ignore
        [vTooltip, showDeployButton, deployButtonDisabled, onDeployClick,];
    }
    // @ts-ignore
    [];
    var __VLS_45;
    var __VLS_46;
}
if (__VLS_ctx.showCompareButton) {
    let __VLS_56;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent1(__VLS_56, new __VLS_56({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
        disabled: (__VLS_ctx.compareButtonDisabled),
    }));
    const __VLS_58 = __VLS_57({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
        disabled: (__VLS_ctx.compareButtonDisabled),
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    let __VLS_61;
    const __VLS_62 = ({ click: {} },
        { onClick: (__VLS_ctx.compareClick) });
    __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, value: ('Compare') }, null, null);
    const { default: __VLS_63 } = __VLS_59.slots;
    {
        const { icon: __VLS_64 } = __VLS_59.slots;
        let __VLS_65;
        /** @ts-ignore @type { | typeof __VLS_components.Repeat} */
        Repeat;
        // @ts-ignore
        const __VLS_66 = __VLS_asFunctionalComponent1(__VLS_65, new __VLS_65({
            size: (14),
        }));
        const __VLS_67 = __VLS_66({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_66));
        // @ts-ignore
        [vTooltip, showCompareButton, compareButtonDisabled, compareClick,];
    }
    // @ts-ignore
    [];
    var __VLS_59;
    var __VLS_60;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar-right" },
});
/** @type {__VLS_StyleScopedClasses['toolbar-right']} */ ;
const __VLS_70 = MetricsSelect;
// @ts-ignore
const __VLS_71 = __VLS_asFunctionalComponent1(__VLS_70, new __VLS_70({
    modelValue: (__VLS_ctx.selectedMetrics),
    metrics: (__VLS_ctx.metrics),
}));
const __VLS_72 = __VLS_71({
    modelValue: (__VLS_ctx.selectedMetrics),
    metrics: (__VLS_ctx.metrics),
}, ...__VLS_functionalComponentArgsRest(__VLS_71));
if (__VLS_ctx.modelForEdit) {
    const __VLS_75 = ArtifactEditor || ArtifactEditor;
    // @ts-ignore
    const __VLS_76 = __VLS_asFunctionalComponent1(__VLS_75, new __VLS_75({
        ...{ 'onUpdate:visible': {} },
        visible: (!!__VLS_ctx.modelForEdit),
        data: (__VLS_ctx.modelForEdit),
    }));
    const __VLS_77 = __VLS_76({
        ...{ 'onUpdate:visible': {} },
        visible: (!!__VLS_ctx.modelForEdit),
        data: (__VLS_ctx.modelForEdit),
    }, ...__VLS_functionalComponentArgsRest(__VLS_76));
    let __VLS_80;
    const __VLS_81 = ({ 'update:visible': {} },
        { 'onUpdate:visible': (...[$event]) => {
                if (!(__VLS_ctx.modelForEdit))
                    return;
                __VLS_ctx.modelForEdit = null;
                // @ts-ignore
                [selectedMetrics, metrics, modelForEdit, modelForEdit, modelForEdit, modelForEdit,];
            } });
    var __VLS_78;
    var __VLS_79;
}
const __VLS_82 = ForceDeleteConfirmDialog || ForceDeleteConfirmDialog;
// @ts-ignore
const __VLS_83 = __VLS_asFunctionalComponent1(__VLS_82, new __VLS_82({
    ...{ 'onConfirm': {} },
    visible: (__VLS_ctx.isForceDeleting),
    title: (__VLS_ctx.forceDeleteTitle),
    text: (__VLS_ctx.FORCE_DELETE_TEXT),
    loading: (__VLS_ctx.loading),
}));
const __VLS_84 = __VLS_83({
    ...{ 'onConfirm': {} },
    visible: (__VLS_ctx.isForceDeleting),
    title: (__VLS_ctx.forceDeleteTitle),
    text: (__VLS_ctx.FORCE_DELETE_TEXT),
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_83));
let __VLS_87;
const __VLS_88 = ({ confirm: {} },
    { onConfirm: (__VLS_ctx.onForceDelete) });
var __VLS_85;
var __VLS_86;
if (__VLS_ctx.modelForDeployment) {
    const __VLS_89 = DeploymentsCreateModal || DeploymentsCreateModal;
    // @ts-ignore
    const __VLS_90 = __VLS_asFunctionalComponent1(__VLS_89, new __VLS_89({
        ...{ 'onUpdate:visible': {} },
        visible: (!!__VLS_ctx.modelForDeployment),
        initialCollectionId: (__VLS_ctx.collectionsStore.currentCollection?.id),
        initialModelId: (__VLS_ctx.modelForDeployment),
    }));
    const __VLS_91 = __VLS_90({
        ...{ 'onUpdate:visible': {} },
        visible: (!!__VLS_ctx.modelForDeployment),
        initialCollectionId: (__VLS_ctx.collectionsStore.currentCollection?.id),
        initialModelId: (__VLS_ctx.modelForDeployment),
    }, ...__VLS_functionalComponentArgsRest(__VLS_90));
    let __VLS_94;
    const __VLS_95 = ({ 'update:visible': {} },
        { 'onUpdate:visible': (__VLS_ctx.onUpdateModelDeploymentVisible) });
    var __VLS_92;
    var __VLS_93;
}
// @ts-ignore
[isForceDeleting, forceDeleteTitle, FORCE_DELETE_TEXT, loading, onForceDelete, modelForDeployment, modelForDeployment, modelForDeployment, collectionsStore, onUpdateModelDeploymentVisible,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
