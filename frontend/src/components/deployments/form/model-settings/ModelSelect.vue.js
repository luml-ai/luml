/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useArtifactsList } from '@/hooks/useArtifactsList';
import { Select } from 'primevue';
import { computed, watch } from 'vue';
import { useArtifactsStore } from '@/stores/artifacts';
import { getErrorMessage } from '@/helpers/helpers';
import { useToast } from 'primevue';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces';
const ARTIFACT_TYPES = [ArtifactTypeEnum.model];
const { setRequestInfo, getInitialPage, list, reset, addItemsToList, onLazyLoad } = useArtifactsList(20, false, ARTIFACT_TYPES);
const artifactsStore = useArtifactsStore();
const toast = useToast();
const virtualScrollerOptions = computed(() => {
    if (list.value.length < 10)
        return undefined;
    return { lazy: true, onLazyLoad: onLazyLoad, itemSize: 38 };
});
const props = defineProps();
const modelValue = defineModel('modelValue');
async function addInitialModelToList(modelId) {
    const model = await artifactsStore.getArtifact(modelId);
    addItemsToList([model]);
}
async function onRequestInfoChange() {
    try {
        reset();
        if (props.initialModelId) {
            addInitialModelToList(props.initialModelId);
        }
        if (!props.collectionId)
            return;
        setRequestInfo({
            organizationId: props.organizationId,
            orbitId: props.orbitId,
            collectionId: props.collectionId,
        });
        await getInitialPage();
    }
    catch (e) {
        const message = getErrorMessage(e, 'Failed to load models');
        toast.add(simpleErrorToast(message));
    }
}
watch(() => [props.organizationId, props.orbitId, props.collectionId], onRequestInfoChange, {
    immediate: true,
    deep: true,
});
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
    ...{ class: "field" },
    ...{ style: {} },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "modelId",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.modelValue),
    id: "modelId",
    name: "modelId",
    placeholder: "Select model",
    fluid: true,
    options: (__VLS_ctx.list),
    optionLabel: "name",
    optionValue: "id",
    disabled: (__VLS_ctx.disabled),
    virtualScrollerOptions: (__VLS_ctx.virtualScrollerOptions),
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.modelValue),
    id: "modelId",
    name: "modelId",
    placeholder: "Select model",
    fluid: true,
    options: (__VLS_ctx.list),
    optionLabel: "name",
    optionValue: "id",
    disabled: (__VLS_ctx.disabled),
    virtualScrollerOptions: (__VLS_ctx.virtualScrollerOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_3.slots;
{
    const { header: __VLS_6 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "dropdown-title" },
    });
    /** @type {__VLS_StyleScopedClasses['dropdown-title']} */ ;
    // @ts-ignore
    [modelValue, list, disabled, virtualScrollerOptions,];
}
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
