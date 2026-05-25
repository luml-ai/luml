/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ExperimentSnapshot } from '@luml/experiments';
import { computed, onBeforeMount, ref } from 'vue';
import { useArtifactsStore } from '@/stores/artifacts';
import { Skeleton } from 'primevue';
import { useExperimentSnapshotsDatabaseProvider } from '@/hooks/useExperimentSnapshotsDatabaseProvider';
import { getArtifactColorByIndex } from '@/helpers/helpers';
import { useThemeStore } from '@/stores/theme';
const artifactsStore = useArtifactsStore();
const { init } = useExperimentSnapshotsDatabaseProvider();
const themeStore = useThemeStore();
const loading = ref(true);
const artifactsInfo = computed(() => {
    const data = {};
    if (artifactsStore.currentArtifact) {
        data[artifactsStore.currentArtifact.id] = {
            name: artifactsStore.currentArtifact.name,
            color: getArtifactColorByIndex(0),
        };
    }
    return data;
});
onBeforeMount(async () => {
    if (artifactsStore.experimentSnapshotProvider) {
        loading.value = false;
        return;
    }
    try {
        loading.value = true;
        if (!artifactsStore.currentArtifact)
            throw new Error('Current artifact does not exist');
        await init([artifactsStore.currentArtifact]);
    }
    catch (e) {
        console.error(e);
    }
    finally {
        loading.value = false;
    }
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.Skeleton | typeof __VLS_components.Skeleton} */
    Skeleton;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ style: {} },
    }));
    const __VLS_2 = __VLS_1({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ style: {} },
    });
    let __VLS_5;
    /** @ts-ignore @type { | typeof __VLS_components.Skeleton | typeof __VLS_components.Skeleton} */
    Skeleton;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        ...{ style: {} },
    }));
    const __VLS_7 = __VLS_6({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
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
}
if (__VLS_ctx.artifactsStore.experimentSnapshotProvider && __VLS_ctx.artifactsStore.currentArtifact) {
    let __VLS_20;
    /** @ts-ignore @type { | typeof __VLS_components.ExperimentSnapshot | typeof __VLS_components.ExperimentSnapshot} */
    ExperimentSnapshot;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
        provider: (__VLS_ctx.artifactsStore.experimentSnapshotProvider),
        modelsIds: ([String(__VLS_ctx.artifactsStore.currentArtifact.id)]),
        modelsInfo: (__VLS_ctx.artifactsInfo),
        theme: (__VLS_ctx.themeStore.getCurrentTheme),
    }));
    const __VLS_22 = __VLS_21({
        provider: (__VLS_ctx.artifactsStore.experimentSnapshotProvider),
        modelsIds: ([String(__VLS_ctx.artifactsStore.currentArtifact.id)]),
        modelsInfo: (__VLS_ctx.artifactsInfo),
        theme: (__VLS_ctx.themeStore.getCurrentTheme),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
}
// @ts-ignore
[loading, artifactsStore, artifactsStore, artifactsStore, artifactsStore, artifactsInfo, themeStore,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
