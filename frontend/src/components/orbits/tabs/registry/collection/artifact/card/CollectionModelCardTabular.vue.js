/// <reference types="../../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { FnnxService } from '@/lib/fnnx/FnnxService';
import { computed } from 'vue';
import ModelTabularPerformance from '@/components/model/ModelTabularPerformance.vue';
const props = defineProps();
const features = computed(() => {
    return FnnxService.getTop5TabularFeatures(props.metrics);
});
const totalScore = computed(() => {
    return FnnxService.getTabularTotalScore(props.metrics);
});
const testMetrics = computed(() => {
    return FnnxService.prepareTabularMetrics(props.metrics.performance.eval_cv || props.metrics.performance.eval_holdout, props.tag);
});
const trainMetrics = computed(() => {
    return FnnxService.prepareTabularMetrics(props.metrics.performance.train, props.tag);
});
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['model-info']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "model-info" },
});
/** @type {__VLS_StyleScopedClasses['model-info']} */ ;
const __VLS_0 = ModelTabularPerformance || ModelTabularPerformance;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    totalScore: (__VLS_ctx.totalScore),
    testMetrics: (__VLS_ctx.testMetrics),
    trainingMetrics: (__VLS_ctx.trainMetrics),
    tag: (__VLS_ctx.tag),
    gridMetrics: true,
}));
const __VLS_2 = __VLS_1({
    totalScore: (__VLS_ctx.totalScore),
    testMetrics: (__VLS_ctx.testMetrics),
    trainingMetrics: (__VLS_ctx.trainMetrics),
    tag: (__VLS_ctx.tag),
    gridMetrics: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "features card" },
});
/** @type {__VLS_StyleScopedClasses['features']} */ ;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "card-header" },
});
/** @type {__VLS_StyleScopedClasses['card-header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "card-title" },
});
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
(__VLS_ctx.features.length + 1);
__VLS_asFunctionalElement1(__VLS_intrinsics.ol, __VLS_intrinsics.ol)({
    ...{ class: "features-list" },
});
/** @type {__VLS_StyleScopedClasses['features-list']} */ ;
for (const [feature, index] of __VLS_vFor((__VLS_ctx.features))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        key: (feature.feature_name),
        ...{ class: "feature" },
    });
    /** @type {__VLS_StyleScopedClasses['feature']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "feature__count" },
    });
    /** @type {__VLS_StyleScopedClasses['feature__count']} */ ;
    (index + 1);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "feature__name" },
    });
    /** @type {__VLS_StyleScopedClasses['feature__name']} */ ;
    (feature.feature_name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "feature__value" },
    });
    /** @type {__VLS_StyleScopedClasses['feature__value']} */ ;
    (feature.scaled_importance);
    // @ts-ignore
    [totalScore, testMetrics, trainMetrics, tag, features, features,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
