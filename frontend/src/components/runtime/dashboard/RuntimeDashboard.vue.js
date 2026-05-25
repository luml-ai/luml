/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, watch } from 'vue';
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService';
import TabularTask from './tabular/index.vue';
import RuntimeDashboardPromptOptimization from './prompt-optimization/RuntimeDashboardPromptOptimization.vue';
import { useRouteLeaveConfirm } from '@/hooks/useRouteLeaveConfirm';
import { leavePageConfirmOptions } from '@/lib/primevue/data/confirm';
const { setGuard } = useRouteLeaveConfirm(leavePageConfirmOptions(() => { }));
const props = defineProps();
const __VLS_emit = defineEmits();
const component = computed(() => {
    if ([
        FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1,
        FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1,
    ].includes(props.currentTag)) {
        return TabularTask;
    }
    else if ([FNNX_PRODUCER_TAGS_MANIFEST_ENUM.prompt_optimization_v1].includes(props.currentTag)) {
        return RuntimeDashboardPromptOptimization;
    }
    return null;
});
watch(component, (value) => {
    setGuard(!!value);
}, { immediate: true });
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
if (__VLS_ctx.component) {
    const __VLS_0 = (__VLS_ctx.component);
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onFinish': {} },
        model: (__VLS_ctx.model),
        currentTag: (__VLS_ctx.currentTag),
        modelId: (__VLS_ctx.modelId),
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onFinish': {} },
        model: (__VLS_ctx.model),
        currentTag: (__VLS_ctx.currentTag),
        modelId: (__VLS_ctx.modelId),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ finish: {} },
        { onFinish: (...[$event]) => {
                if (!(__VLS_ctx.component))
                    return;
                __VLS_ctx.$emit('exit');
                // @ts-ignore
                [component, component, model, currentTag, modelId, $emit,];
            } });
    var __VLS_7;
    var __VLS_3;
    var __VLS_4;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "placeholder" },
    });
    /** @type {__VLS_StyleScopedClasses['placeholder']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "title" },
    });
    /** @type {__VLS_StyleScopedClasses['title']} */ ;
    let __VLS_8;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        ...{ 'onClick': {} },
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_13;
    const __VLS_14 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!!(__VLS_ctx.component))
                    return;
                __VLS_ctx.$emit('exit');
                // @ts-ignore
                [$emit,];
            } });
    const { default: __VLS_15 } = __VLS_11.slots;
    // @ts-ignore
    [];
    var __VLS_11;
    var __VLS_12;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
