/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { getRadialBarOptions } from '@/lib/apex-charts/apex-charts';
import MetricCard from '@/components/ui/MetricCard.vue';
const __VLS_props = defineProps();
const totalScoreOptions = ref(getRadialBarOptions());
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "radialbar-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['radialbar-wrapper']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.apexchart | typeof __VLS_components.Apexchart} */
apexchart;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    type: "radialBar",
    series: ([__VLS_ctx.totalScore]),
    options: (__VLS_ctx.totalScoreOptions),
    ...{ style: ({ pointerEvents: 'none', marginTop: '-30px', height: '135px' }) },
}));
const __VLS_2 = __VLS_1({
    type: "radialBar",
    series: ([__VLS_ctx.totalScore]),
    options: (__VLS_ctx.totalScoreOptions),
    ...{ style: ({ pointerEvents: 'none', marginTop: '-30px', height: '135px' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "metrics" },
});
/** @type {__VLS_StyleScopedClasses['metrics']} */ ;
for (const [card] of __VLS_vFor((__VLS_ctx.metrics))) {
    const __VLS_5 = MetricCard;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        key: (card.title),
        title: (card.title),
        items: (card.items),
    }));
    const __VLS_7 = __VLS_6({
        key: (card.title),
        title: (card.title),
        items: (card.items),
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    // @ts-ignore
    [totalScore, totalScoreOptions, metrics,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
