/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref } from 'vue';
import FileInput from '../ui/FileInput.vue';
import { ArrowRight } from 'lucide-vue-next';
import { predictErrorToast } from '@/lib/primevue/data/toasts';
import { useToast } from 'primevue';
const toast = useToast();
const props = defineProps();
const __VLS_emit = defineEmits();
const file = ref({});
const isModelLoading = ref(false);
const isError = ref(false);
const isContinueAvailable = computed(() => !!file.value.name);
async function selectFile(event) {
    isError.value = false;
    isModelLoading.value = true;
    try {
        await props.uploadCallback(event);
        file.value = {
            name: event.name,
            size: event.size,
        };
    }
    catch (e) {
        toast.add(predictErrorToast(e));
        isError.value = true;
    }
    finally {
        isModelLoading.value = false;
    }
}
function removeFile() {
    isError.value = false;
    file.value = {};
    props.removeCallback();
}
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
/** @type {__VLS_StyleScopedClasses['middle-divider']} */ ;
/** @type {__VLS_StyleScopedClasses['middle-divider']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "wrapper" },
});
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "title" },
});
/** @type {__VLS_StyleScopedClasses['title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "area" },
});
/** @type {__VLS_StyleScopedClasses['area']} */ ;
const __VLS_0 = FileInput;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onSelectFile': {} },
    ...{ 'onRemoveFile': {} },
    id: "model",
    file: (__VLS_ctx.file),
    error: (__VLS_ctx.isError),
    acceptText: "Accepts .luml files",
    uploadText: "upload a model",
    loading: (__VLS_ctx.isModelLoading),
    loadingMessage: "Model creating...",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onSelectFile': {} },
    ...{ 'onRemoveFile': {} },
    id: "model",
    file: (__VLS_ctx.file),
    error: (__VLS_ctx.isError),
    acceptText: "Accepts .luml files",
    uploadText: "upload a model",
    loading: (__VLS_ctx.isModelLoading),
    loadingMessage: "Model creating...",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ selectFile: {} },
    { onSelectFile: (__VLS_ctx.selectFile) });
const __VLS_7 = ({ removeFile: {} },
    { onRemoveFile: (__VLS_ctx.removeFile) });
var __VLS_3;
var __VLS_4;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "middle-divider" },
});
/** @type {__VLS_StyleScopedClasses['middle-divider']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sample" },
});
/** @type {__VLS_StyleScopedClasses['sample']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sample-title" },
});
/** @type {__VLS_StyleScopedClasses['sample-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    ...{ 'onClick': {} },
    label: "Express tasks",
}));
const __VLS_10 = __VLS_9({
    ...{ 'onClick': {} },
    label: "Express tasks",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
let __VLS_13;
const __VLS_14 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.$router.push({ name: 'home' });
            // @ts-ignore
            [file, isError, isModelLoading, selectFile, removeFile, $router,];
        } });
var __VLS_11;
var __VLS_12;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "navigation" },
});
/** @type {__VLS_StyleScopedClasses['navigation']} */ ;
let __VLS_15;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    ...{ 'onClick': {} },
    disabled: (!__VLS_ctx.isContinueAvailable),
}));
const __VLS_17 = __VLS_16({
    ...{ 'onClick': {} },
    disabled: (!__VLS_ctx.isContinueAvailable),
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
let __VLS_20;
const __VLS_21 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.$emit('continue');
            // @ts-ignore
            [isContinueAvailable, $emit,];
        } });
const { default: __VLS_22 } = __VLS_18.slots;
let __VLS_23;
/** @ts-ignore @type { | typeof __VLS_components.ArrowRight} */
ArrowRight;
// @ts-ignore
const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
    width: "14",
    height: "14",
}));
const __VLS_25 = __VLS_24({
    width: "14",
    height: "14",
}, ...__VLS_functionalComponentArgsRest(__VLS_24));
// @ts-ignore
[];
var __VLS_18;
var __VLS_19;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
