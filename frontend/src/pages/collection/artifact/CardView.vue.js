/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, onMounted, ref } from 'vue';
import { useArtifactsStore } from '@/stores/artifacts';
import { ProgressSpinner } from 'primevue';
import { FnnxService } from '@/lib/fnnx/FnnxService';
import { ModelDownloader } from '@/lib/bucket-service';
import JSZip from 'jszip';
import CollectionModelCardTabular from '@/components/orbits/tabs/registry/collection/artifact/card/CollectionModelCardTabular.vue';
import CollectionModelCardPromptOptimization from '@/components/orbits/tabs/registry/collection/artifact/card/CollectionModelCardPromptOptimization.vue';
import CollectionModelCardHtml from '@/components/orbits/tabs/registry/collection/artifact/card/CollectionModelCardHtml.vue';
const artifactsStore = useArtifactsStore();
const loading = ref(false);
const isTabular = computed(() => artifactsStore.currentModelTag && FnnxService.isTabularTag(artifactsStore.currentModelTag));
const isPromptOptimization = computed(() => artifactsStore.currentModelTag &&
    FnnxService.isPromptOptimizationTag(artifactsStore.currentModelTag));
function setTabularMetadata(file) {
    const metrics = FnnxService.getTabularMetrics(file);
    artifactsStore.setCurrentModelMetadata({ metrics });
}
function setPromptOptimizationMetadata(file) {
    const data = FnnxService.getPromptOptimizationData(file);
    artifactsStore.setCurrentModelMetadata(data);
}
async function setHtmlData(model) {
    const htmlArchiveName = FnnxService.findHtmlCard(model.file_index);
    if (!htmlArchiveName)
        return;
    const url = await artifactsStore.getDownloadUrl(model.id);
    const modelDownloader = new ModelDownloader(url);
    const arrayBuffer = await modelDownloader.getFileFromBucket(model.file_index, htmlArchiveName, true);
    const zip = await JSZip.loadAsync(arrayBuffer);
    const rawFile = await zip.file(Object.keys(zip.files)[0])?.async('arraybuffer');
    if (!rawFile)
        throw new Error('File not found');
    const decoder = new TextDecoder('utf-8');
    let fileString = decoder.decode(rawFile);
    if (!fileString.includes('<meta charset=')) {
        fileString = fileString.replace(/<head>/i, `<head>
        <meta charset="UTF-8">`);
    }
    const blob = new Blob([fileString], { type: 'text/html' });
    const blobUrl = URL.createObjectURL(blob);
    artifactsStore.setCurrentModelHtmlBlobUrl(blobUrl);
}
async function setLumlMetadata(tag, model) {
    const metadataFileName = FnnxService.getModelMetadataFileName(model.file_index);
    if (!metadataFileName)
        return;
    artifactsStore.setCurrentModelTag(tag);
    const url = await artifactsStore.getDownloadUrl(model.id);
    const modelDownloader = new ModelDownloader(url);
    const file = await modelDownloader.getFileFromBucket(model.file_index, metadataFileName);
    if (FnnxService.isTabularTag(tag)) {
        setTabularMetadata(file);
    }
    else if (FnnxService.isPromptOptimizationTag(tag)) {
        setPromptOptimizationMetadata(file);
    }
}
async function setMetadata() {
    const model = artifactsStore.currentArtifact;
    if (!model)
        throw new Error('Current model does not exist');
    const currentTag = FnnxService.getTypeTag(model.manifest);
    if (currentTag) {
        await setLumlMetadata(currentTag, model);
    }
    else {
        await setHtmlData(model);
    }
}
async function init() {
    try {
        loading.value = true;
        await setMetadata();
    }
    catch (e) {
        console.error(e);
    }
    finally {
        loading.value = false;
    }
}
onMounted(async () => {
    if (artifactsStore.currentModelMetadata || artifactsStore.currentModelHtmlBlobUrl)
        return;
    init();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "loading-block" },
    });
    /** @type {__VLS_StyleScopedClasses['loading-block']} */ ;
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.ProgressSpinner | typeof __VLS_components.ProgressSpinner} */
    ProgressSpinner;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
    const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
else if (__VLS_ctx.artifactsStore.currentModelMetadata && __VLS_ctx.artifactsStore.currentModelTag) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    if (__VLS_ctx.isTabular && 'metrics' in __VLS_ctx.artifactsStore.currentModelMetadata) {
        const __VLS_5 = CollectionModelCardTabular || CollectionModelCardTabular;
        // @ts-ignore
        const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
            metrics: (__VLS_ctx.artifactsStore.currentModelMetadata.metrics),
            tag: (__VLS_ctx.artifactsStore.currentModelTag),
        }));
        const __VLS_7 = __VLS_6({
            metrics: (__VLS_ctx.artifactsStore.currentModelMetadata.metrics),
            tag: (__VLS_ctx.artifactsStore.currentModelTag),
        }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    }
    else if (__VLS_ctx.isPromptOptimization && 'edges' in __VLS_ctx.artifactsStore.currentModelMetadata) {
        const __VLS_10 = CollectionModelCardPromptOptimization || CollectionModelCardPromptOptimization;
        // @ts-ignore
        const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
            data: (__VLS_ctx.artifactsStore.currentModelMetadata),
        }));
        const __VLS_12 = __VLS_11({
            data: (__VLS_ctx.artifactsStore.currentModelMetadata),
        }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "card" },
        });
        /** @type {__VLS_StyleScopedClasses['card']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
            ...{ class: "card-header" },
        });
        /** @type {__VLS_StyleScopedClasses['card-header']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
            ...{ class: "card-title card-title--medium" },
        });
        /** @type {__VLS_StyleScopedClasses['card-title']} */ ;
        /** @type {__VLS_StyleScopedClasses['card-title--medium']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        (__VLS_ctx.artifactsStore.currentArtifact?.manifest.producer_tags);
    }
}
else if (__VLS_ctx.artifactsStore.currentModelHtmlBlobUrl) {
    const __VLS_15 = CollectionModelCardHtml || CollectionModelCardHtml;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
        url: (__VLS_ctx.artifactsStore.currentModelHtmlBlobUrl),
    }));
    const __VLS_17 = __VLS_16({
        url: (__VLS_ctx.artifactsStore.currentModelHtmlBlobUrl),
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    var __VLS_20;
    var __VLS_18;
}
// @ts-ignore
[loading, artifactsStore, artifactsStore, artifactsStore, artifactsStore, artifactsStore, artifactsStore, artifactsStore, artifactsStore, artifactsStore, artifactsStore, isTabular, isPromptOptimization,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
