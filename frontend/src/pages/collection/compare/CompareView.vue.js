/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ComparisonHeader, ComparisonModelsList, ExperimentSnapshot } from '@luml/experiments';
import { computed, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useArtifactsStore } from '@/stores/artifacts';
import { useExperimentSnapshotsDatabaseProvider } from '@/hooks/useExperimentSnapshotsDatabaseProvider';
import { Skeleton } from 'primevue';
import { getArtifactColorByIndex } from '@/helpers/helpers';
import { useThemeStore } from '@/stores/theme';
const route = useRoute();
const themeStore = useThemeStore();
const artifactsStore = useArtifactsStore();
const { init } = useExperimentSnapshotsDatabaseProvider();
const loading = ref(false);
const artifactIdsList = computed(() => {
    if (!route.query.artifacts)
        return [];
    if (Array.isArray(route.query.artifacts)) {
        return route.query.artifacts.filter((artifact) => artifact !== null).map(String);
    }
    return [String(route.query.artifacts)];
});
const artifactsList = ref([]);
const artifactsInfo = computed(() => {
    return artifactsList.value.reduce((acc, artifact, index) => {
        const name = artifact.name;
        const color = getArtifactColorByIndex(index);
        acc[artifact.id] = { name, color };
        return acc;
    }, {});
});
async function onArtifactIdsChange(newArtifactIds) {
    try {
        loading.value = true;
        artifactsStore.resetExperimentSnapshotProvider();
        artifactsList.value = [];
        const promises = await Promise.allSettled(newArtifactIds.map((artifactId) => artifactsStore.getArtifact(artifactId)));
        const artifacts = promises
            .map((promise) => (promise.status === 'fulfilled' ? promise.value : null))
            .filter((artifact) => !!artifact);
        artifactsList.value = artifacts;
        await init(artifactsList.value);
    }
    catch (e) {
        console.error(e);
    }
    finally {
        loading.value = false;
    }
}
onUnmounted(() => {
    artifactsStore.resetExperimentSnapshotProvider();
});
watch(artifactIdsList, onArtifactIdsChange, { immediate: true, deep: true });
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.ComparisonHeader | typeof __VLS_components.ComparisonHeader} */
ComparisonHeader;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.ComparisonModelsList | typeof __VLS_components.ComparisonModelsList} */
ComparisonModelsList;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    modelsIds: (__VLS_ctx.artifactIdsList),
    modelsList: (__VLS_ctx.artifactsList),
    modelsInfo: (__VLS_ctx.artifactsInfo),
}));
const __VLS_7 = __VLS_6({
    modelsIds: (__VLS_ctx.artifactIdsList),
    modelsList: (__VLS_ctx.artifactsList),
    modelsInfo: (__VLS_ctx.artifactsInfo),
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.Skeleton | typeof __VLS_components.Skeleton} */
    Skeleton;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        ...{ style: {} },
    }));
    const __VLS_12 = __VLS_11({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ style: {} },
    });
    let __VLS_15;
    /** @ts-ignore @type { | typeof __VLS_components.Skeleton | typeof __VLS_components.Skeleton} */
    Skeleton;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
        ...{ style: {} },
    }));
    const __VLS_17 = __VLS_16({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    let __VLS_20;
    /** @ts-ignore @type { | typeof __VLS_components.Skeleton | typeof __VLS_components.Skeleton} */
    Skeleton;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
        ...{ style: {} },
    }));
    const __VLS_22 = __VLS_21({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    let __VLS_25;
    /** @ts-ignore @type { | typeof __VLS_components.Skeleton | typeof __VLS_components.Skeleton} */
    Skeleton;
    // @ts-ignore
    const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
        ...{ style: {} },
    }));
    const __VLS_27 = __VLS_26({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_26));
}
else if (__VLS_ctx.artifactsStore.experimentSnapshotProvider) {
    let __VLS_30;
    /** @ts-ignore @type { | typeof __VLS_components.ExperimentSnapshot | typeof __VLS_components.ExperimentSnapshot} */
    ExperimentSnapshot;
    // @ts-ignore
    const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
        provider: (__VLS_ctx.artifactsStore.experimentSnapshotProvider),
        modelsIds: (__VLS_ctx.artifactIdsList),
        modelsInfo: (__VLS_ctx.artifactsInfo),
        theme: (__VLS_ctx.themeStore.getCurrentTheme),
    }));
    const __VLS_32 = __VLS_31({
        provider: (__VLS_ctx.artifactsStore.experimentSnapshotProvider),
        modelsIds: (__VLS_ctx.artifactIdsList),
        modelsInfo: (__VLS_ctx.artifactsInfo),
        theme: (__VLS_ctx.themeStore.getCurrentTheme),
    }, ...__VLS_functionalComponentArgsRest(__VLS_31));
}
// @ts-ignore
[artifactIdsList, artifactIdsList, artifactsList, artifactsInfo, artifactsInfo, loading, artifactsStore, artifactsStore, themeStore,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
