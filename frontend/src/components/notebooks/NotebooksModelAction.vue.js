/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { SplitButton } from 'primevue';
import { CloudDownload } from 'lucide-vue-next';
import { DatabaseService } from '@/lib/databases/DatabaseService';
import { downloadFileFromBlob } from '@/helpers/helpers';
import { useOrganizationStore } from '@/stores/organization';
import ModelUpload from '../model-upload/ModelUpload.vue';
import { ref } from 'vue';
const props = defineProps();
const organizationStore = useOrganizationStore();
const modelBlob = ref(null);
const modelUploadVisible = ref(false);
const EXPORT_ITEMS = [
    {
        label: 'Upload to Registry',
        command: openModelUpload,
        disabled: () => !organizationStore.currentOrganization,
    },
    {
        label: 'Download model',
        command: downloadFile,
    },
];
async function downloadFile() {
    const blob = await DatabaseService.getFileBlob(props.file);
    downloadFileFromBlob(blob, props.file.name);
}
async function openModelUpload() {
    modelBlob.value = await DatabaseService.getFileBlob(props.file);
    modelUploadVisible.value = true;
}
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.SplitButton | typeof __VLS_components.SplitButton} */
SplitButton;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    severity: "secondary",
    model: (__VLS_ctx.EXPORT_ITEMS),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    severity: "secondary",
    model: (__VLS_ctx.EXPORT_ITEMS),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.downloadFile();
            // @ts-ignore
            [EXPORT_ITEMS, downloadFile,];
        } });
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { icon: __VLS_8 } = __VLS_3.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.CloudDownload} */
    CloudDownload;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        size: (14),
    }));
    const __VLS_11 = __VLS_10({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
if (__VLS_ctx.modelBlob && !!__VLS_ctx.organizationStore.currentOrganization) {
    const __VLS_14 = ModelUpload || ModelUpload;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        modelBlob: (__VLS_ctx.modelBlob),
        visible: (__VLS_ctx.modelUploadVisible),
        fileName: (__VLS_ctx.file.name),
    }));
    const __VLS_16 = __VLS_15({
        modelBlob: (__VLS_ctx.modelBlob),
        visible: (__VLS_ctx.modelUploadVisible),
        fileName: (__VLS_ctx.file.name),
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
}
// @ts-ignore
[modelBlob, modelBlob, organizationStore, modelUploadVisible, file,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
