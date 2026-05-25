/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces';
import { useArtifactsStore } from '@/stores/artifacts';
import { computed, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { FnnxService } from '@/lib/fnnx/FnnxService';
import { Button, useToast } from 'primevue';
import { Bolt, Rocket, Download } from 'lucide-vue-next';
import { useOrbitsStore } from '@/stores/orbits';
import { PermissionEnum } from '@/lib/api/api.interfaces';
import { useCollectionsStore } from '@/stores/collections';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { getErrorMessage } from '@/helpers/helpers';
import { useDatasetsStore } from '@/stores/datasets';
import ArtifactTabs from '@/components/orbits/tabs/registry/collection/artifact/ArtifactTabs.vue';
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue';
import ArtifactEditor from '@/components/orbits/tabs/registry/collection/artifact/ArtifactEditor.vue';
const artifactsStore = useArtifactsStore();
const route = useRoute();
const router = useRouter();
const orbitsStore = useOrbitsStore();
const collectionsStore = useCollectionsStore();
const toast = useToast();
const datasetsStore = useDatasetsStore();
const modelForDeployment = ref(null);
const modelForEdit = ref(null);
const isDeployButtonVisible = computed(() => {
    return artifactsStore.currentArtifact?.type === ArtifactTypeEnum.model;
});
const isDataTabVisible = computed(() => {
    if (!artifactsStore.currentArtifact)
        return false;
    return artifactsStore.currentArtifact.type === ArtifactTypeEnum.dataset;
});
const isExperimentSnapshotVisible = computed(() => {
    if (!artifactsStore.currentArtifact)
        return false;
    return (artifactsStore.currentArtifact.type === ArtifactTypeEnum.experiment ||
        artifactsStore.currentArtifact.type === ArtifactTypeEnum.model);
});
const isModelAttachmentsVisible = computed(() => {
    if (!artifactsStore.currentArtifact)
        return false;
    return (artifactsStore.currentArtifact.type === ArtifactTypeEnum.model ||
        artifactsStore.currentArtifact.type === ArtifactTypeEnum.experiment);
});
const isCardAvailable = computed(() => {
    if (!artifactsStore.currentArtifact)
        return false;
    const fileIndex = artifactsStore.currentArtifact.file_index;
    const includeSupportedTag = FnnxService.getTypeTag(artifactsStore.currentArtifact.manifest);
    return !!(includeSupportedTag || FnnxService.findHtmlCard(fileIndex));
});
const isExperimentSnapshotCardAvailable = computed(() => {
    if (!artifactsStore.currentArtifact)
        return false;
    const fileIndex = artifactsStore.currentArtifact.file_index;
    return !!FnnxService.findExperimentSnapshotArchiveName(fileIndex);
});
const isModelAttachmentsAvailable = computed(() => {
    if (!artifactsStore.currentArtifact)
        return false;
    const fileIndex = artifactsStore.currentArtifact.file_index;
    if (!fileIndex)
        return false;
    return FnnxService.hasAttachments(fileIndex);
});
function initDeploy() {
    if (artifactsStore.currentArtifact) {
        modelForDeployment.value = artifactsStore.currentArtifact.id;
    }
}
function openModelEditor() {
    const m = artifactsStore.currentArtifact;
    if (!m)
        return;
    modelForEdit.value = {
        ...m,
    };
}
function onUpdateModelDeploymentVisible(val) {
    if (!val)
        modelForDeployment.value = null;
}
function onUpdateModelEditorVisible(val) {
    if (!val)
        modelForEdit.value = null;
}
function onModelDeleted() {
    artifactsStore.resetCurrentArtifact();
    navigateToArtifactsList();
}
function onUpdateModel(model) {
    artifactsStore.setCurrentArtifact(model);
}
function navigateToArtifactsList() {
    router.replace({
        name: 'collection',
        params: {
            organizationId: route.params.organizationId,
            id: route.params.id,
            collectionId: route.params.collectionId,
        },
    });
}
async function downloadClick() {
    if (!artifactsStore.currentArtifact)
        return;
    try {
        await artifactsStore.downloadArtifact(artifactsStore.currentArtifact.id, artifactsStore.currentArtifact.file_name);
    }
    catch (e) {
        console.error('Download failed', e);
    }
}
async function onArtifactIdChange(artifactId) {
    try {
        artifactsStore.resetCurrentArtifact();
        if (typeof artifactId !== 'string')
            return;
        const requestInfo = {
            organizationId: route.params.organizationId,
            orbitId: route.params.id,
            collectionId: route.params.collectionId,
        };
        const artifact = await artifactsStore.getArtifact(artifactId, requestInfo);
        artifactsStore.setCurrentArtifact(artifact);
    }
    catch (e) {
        const message = getErrorMessage(e, 'Failed to set current artifact');
        toast.add(simpleErrorToast(message));
    }
}
watch(() => route.params.artifactId, onArtifactIdChange, { immediate: true });
onUnmounted(() => {
    artifactsStore.resetCurrentArtifact();
    artifactsStore.resetCurrentModelTag();
    artifactsStore.resetCurrentModelMetadata();
    artifactsStore.resetCurrentModelHtmlBlobUrl();
    artifactsStore.resetExperimentSnapshotProvider();
    datasetsStore.reset();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
if (__VLS_ctx.artifactsStore.currentArtifact) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "header" },
    });
    /** @type {__VLS_StyleScopedClasses['header']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "title" },
    });
    /** @type {__VLS_StyleScopedClasses['title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "toolbar" },
    });
    /** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
    if (__VLS_ctx.orbitsStore.getCurrentOrbitPermissions?.artifact.includes(__VLS_ctx.PermissionEnum.update)) {
        let __VLS_0;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
            ...{ 'onClick': {} },
            variant: "text",
            severity: "secondary",
        }));
        const __VLS_2 = __VLS_1({
            ...{ 'onClick': {} },
            variant: "text",
            severity: "secondary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_1));
        let __VLS_5;
        const __VLS_6 = ({ click: {} },
            { onClick: (__VLS_ctx.openModelEditor) });
        __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, value: ('Settings') }, null, null);
        const { default: __VLS_7 } = __VLS_3.slots;
        {
            const { icon: __VLS_8 } = __VLS_3.slots;
            let __VLS_9;
            /** @ts-ignore @type { | typeof __VLS_components.Bolt} */
            Bolt;
            // @ts-ignore
            const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
                size: (16),
            }));
            const __VLS_11 = __VLS_10({
                size: (16),
            }, ...__VLS_functionalComponentArgsRest(__VLS_10));
            // @ts-ignore
            [artifactsStore, orbitsStore, PermissionEnum, openModelEditor, vTooltip,];
        }
        // @ts-ignore
        [];
        var __VLS_3;
        var __VLS_4;
    }
    if (__VLS_ctx.isDeployButtonVisible) {
        let __VLS_14;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
            ...{ 'onClick': {} },
            variant: "text",
            severity: "secondary",
        }));
        const __VLS_16 = __VLS_15({
            ...{ 'onClick': {} },
            variant: "text",
            severity: "secondary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_15));
        let __VLS_19;
        const __VLS_20 = ({ click: {} },
            { onClick: (__VLS_ctx.initDeploy) });
        __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, value: ('Deploy') }, null, null);
        const { default: __VLS_21 } = __VLS_17.slots;
        {
            const { icon: __VLS_22 } = __VLS_17.slots;
            let __VLS_23;
            /** @ts-ignore @type { | typeof __VLS_components.Rocket} */
            Rocket;
            // @ts-ignore
            const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
                size: (16),
            }));
            const __VLS_25 = __VLS_24({
                size: (16),
            }, ...__VLS_functionalComponentArgsRest(__VLS_24));
            // @ts-ignore
            [vTooltip, isDeployButtonVisible, initDeploy,];
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
    }));
    const __VLS_30 = __VLS_29({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
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
            size: (16),
        }));
        const __VLS_39 = __VLS_38({
            size: (16),
        }, ...__VLS_functionalComponentArgsRest(__VLS_38));
        // @ts-ignore
        [vTooltip, downloadClick,];
    }
    // @ts-ignore
    [];
    var __VLS_31;
    var __VLS_32;
    const __VLS_42 = ArtifactTabs || ArtifactTabs;
    // @ts-ignore
    const __VLS_43 = __VLS_asFunctionalComponent1(__VLS_42, new __VLS_42({
        cardDisabled: (!__VLS_ctx.isCardAvailable),
        experimentSnapshotDisabled: (!__VLS_ctx.isExperimentSnapshotCardAvailable),
        modelAttachmentsDisabled: (!__VLS_ctx.isModelAttachmentsAvailable),
        showDataTab: (__VLS_ctx.isDataTabVisible),
        showCard: (true),
        showExperimentSnapshot: (__VLS_ctx.isExperimentSnapshotVisible),
        showModelAttachments: (__VLS_ctx.isModelAttachmentsVisible),
    }));
    const __VLS_44 = __VLS_43({
        cardDisabled: (!__VLS_ctx.isCardAvailable),
        experimentSnapshotDisabled: (!__VLS_ctx.isExperimentSnapshotCardAvailable),
        modelAttachmentsDisabled: (!__VLS_ctx.isModelAttachmentsAvailable),
        showDataTab: (__VLS_ctx.isDataTabVisible),
        showCard: (true),
        showExperimentSnapshot: (__VLS_ctx.isExperimentSnapshotVisible),
        showModelAttachments: (__VLS_ctx.isModelAttachmentsVisible),
    }, ...__VLS_functionalComponentArgsRest(__VLS_43));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "view-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['view-wrapper']} */ ;
    let __VLS_47;
    /** @ts-ignore @type { | typeof __VLS_components.RouterView | typeof __VLS_components.RouterView} */
    RouterView;
    // @ts-ignore
    const __VLS_48 = __VLS_asFunctionalComponent1(__VLS_47, new __VLS_47({}));
    const __VLS_49 = __VLS_48({}, ...__VLS_functionalComponentArgsRest(__VLS_48));
}
if (__VLS_ctx.modelForDeployment) {
    const __VLS_52 = DeploymentsCreateModal || DeploymentsCreateModal;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent1(__VLS_52, new __VLS_52({
        ...{ 'onUpdate:visible': {} },
        visible: (!!__VLS_ctx.modelForDeployment),
        initialCollectionId: (__VLS_ctx.collectionsStore.currentCollection?.id),
        initialModelId: (__VLS_ctx.modelForDeployment),
    }));
    const __VLS_54 = __VLS_53({
        ...{ 'onUpdate:visible': {} },
        visible: (!!__VLS_ctx.modelForDeployment),
        initialCollectionId: (__VLS_ctx.collectionsStore.currentCollection?.id),
        initialModelId: (__VLS_ctx.modelForDeployment),
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    let __VLS_57;
    const __VLS_58 = ({ 'update:visible': {} },
        { 'onUpdate:visible': (__VLS_ctx.onUpdateModelDeploymentVisible) });
    var __VLS_55;
    var __VLS_56;
}
if (__VLS_ctx.modelForEdit) {
    const __VLS_59 = ArtifactEditor || ArtifactEditor;
    // @ts-ignore
    const __VLS_60 = __VLS_asFunctionalComponent1(__VLS_59, new __VLS_59({
        ...{ 'onUpdate:visible': {} },
        ...{ 'onUpdateArtifact': {} },
        ...{ 'onArtifactDeleted': {} },
        visible: (!!__VLS_ctx.modelForEdit),
        data: (__VLS_ctx.modelForEdit),
    }));
    const __VLS_61 = __VLS_60({
        ...{ 'onUpdate:visible': {} },
        ...{ 'onUpdateArtifact': {} },
        ...{ 'onArtifactDeleted': {} },
        visible: (!!__VLS_ctx.modelForEdit),
        data: (__VLS_ctx.modelForEdit),
    }, ...__VLS_functionalComponentArgsRest(__VLS_60));
    let __VLS_64;
    const __VLS_65 = ({ 'update:visible': {} },
        { 'onUpdate:visible': (__VLS_ctx.onUpdateModelEditorVisible) });
    const __VLS_66 = ({ updateArtifact: {} },
        { onUpdateArtifact: (__VLS_ctx.onUpdateModel) });
    const __VLS_67 = ({ artifactDeleted: {} },
        { onArtifactDeleted: (__VLS_ctx.onModelDeleted) });
    var __VLS_62;
    var __VLS_63;
}
// @ts-ignore
[isCardAvailable, isExperimentSnapshotCardAvailable, isModelAttachmentsAvailable, isDataTabVisible, isExperimentSnapshotVisible, isModelAttachmentsVisible, modelForDeployment, modelForDeployment, modelForDeployment, collectionsStore, onUpdateModelDeploymentVisible, modelForEdit, modelForEdit, modelForEdit, onUpdateModelEditorVisible, onUpdateModel, onModelDeleted,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
