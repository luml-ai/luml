/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ModelAttachments } from '@luml/attachments';
import { onMounted } from 'vue';
import { useArtifactsStore } from '@/stores/artifacts';
import { useTarAttachmentsProvider } from '@/hooks/useTarAttachmentsProvider';
import { ModelDownloader } from '@/lib/bucket-service';
import { FnnxService } from '@/lib/fnnx/FnnxService';
import { getErrorMessage } from '@/helpers/helpers';
import { useToast } from 'primevue';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import UiPageLoader from '@/components/ui/UiPageLoader.vue';
const artifactsStore = useArtifactsStore();
const { provider, loading, init } = useTarAttachmentsProvider();
const toast = useToast();
onMounted(async () => {
    if (provider.value)
        return;
    try {
        if (!artifactsStore.currentArtifact?.file_index) {
            throw new Error('Artifact or file index does not exist');
        }
        const url = await artifactsStore.getDownloadUrl(artifactsStore.currentArtifact.id);
        const downloader = new ModelDownloader(url);
        await init({
            downloader,
            fileIndex: artifactsStore.currentArtifact.file_index,
            findAttachmentsTarPath: FnnxService.findAttachmentsTarPath,
            findAttachmentsIndexPath: FnnxService.findAttachmentsIndexPath,
        });
    }
    catch (e) {
        const message = getErrorMessage(e, 'Failed to initialize attachments');
        toast.add(simpleErrorToast(message));
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
    const __VLS_0 = UiPageLoader;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
    const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
    var __VLS_5;
    var __VLS_3;
}
else if (__VLS_ctx.provider) {
    let __VLS_6;
    /** @ts-ignore @type { | typeof __VLS_components.ModelAttachments} */
    ModelAttachments;
    // @ts-ignore
    const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({
        provider: (__VLS_ctx.provider),
        ...{ class: "attachments" },
    }));
    const __VLS_8 = __VLS_7({
        provider: (__VLS_ctx.provider),
        ...{ class: "attachments" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_7));
    var __VLS_11;
    /** @type {__VLS_StyleScopedClasses['attachments']} */ ;
    var __VLS_9;
}
// @ts-ignore
[loading, provider, provider,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
