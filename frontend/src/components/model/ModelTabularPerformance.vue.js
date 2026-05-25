/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { getRadialBarOptions } from '@/lib/apex-charts/apex-charts';
import { Info } from 'lucide-vue-next';
import { computed, ref } from 'vue';
import { getMetricsCards } from '@/helpers/helpers';
import MetricCard from '../ui/MetricCard.vue';
const props = defineProps();
const options = ref(getRadialBarOptions());
const metricCardsData = computed(() => props.tag ? getMetricsCards(props.testMetrics, props.trainingMetrics, props.tag) : []);
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['radialbar-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "performance card" },
});
/** @type {__VLS_StyleScopedClasses['performance']} */ ;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "card-header" },
});
/** @type {__VLS_StyleScopedClasses['card-header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "card-title" },
});
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Info} */
Info;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    width: "20",
    height: "20",
    ...{ class: "info-icon" },
}));
const __VLS_2 = __VLS_1({
    width: "20",
    height: "20",
    ...{ class: "info-icon" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { bottom: true, }, value: (`Model total score is a custom metric that provides a general estimate of overall model performance. A score around 50% typically indicates random performance, while higher values reflect better predictive ability.`) }, null, null);
/** @type {__VLS_StyleScopedClasses['info-icon']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "radialbar-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['radialbar-wrapper']} */ ;
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.apexchart | typeof __VLS_components.Apexchart} */
apexchart;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    type: "radialBar",
    series: ([__VLS_ctx.totalScore]),
    options: (__VLS_ctx.options),
    ...{ style: ({ pointerEvents: 'none', marginTop: '-30px', height: '135px' }) },
}));
const __VLS_7 = __VLS_6({
    type: "radialBar",
    series: ([__VLS_ctx.totalScore]),
    options: (__VLS_ctx.options),
    ...{ style: ({ pointerEvents: 'none', marginTop: '-30px', height: '135px' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "metric-cards" },
    ...{ class: ({ 'metric-cards--grid': __VLS_ctx.gridMetrics }) },
});
/** @type {__VLS_StyleScopedClasses['metric-cards']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-cards--grid']} */ ;
for (const [card] of __VLS_vFor((__VLS_ctx.metricCardsData))) {
    const __VLS_10 = MetricCard;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        key: (card.title),
        title: (card.title),
        items: (card.items),
    }));
    const __VLS_12 = __VLS_11({
        key: (card.title),
        title: (card.title),
        items: (card.items),
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    // @ts-ignore
    [vTooltip, totalScore, options, gridMetrics, metricCardsData,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
