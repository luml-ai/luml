/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import LayoutHeader from '@/components/layout/LayoutHeader.vue';
import LayoutSidebar from '@/components/layout/LayoutSidebar.vue';
import { Tabs, TabList, Tab } from 'primevue';
import { LayoutDashboard, FolderDot, ScanEye } from 'lucide-vue-next';
import { computed } from 'vue';
const props = defineProps();
const tabsListPT = {
    tabList: { style: 'border-left: none; border-top: none; border-right: none;' },
};
const tabPT = {};
const items = computed(() => [
    {
        label: 'Overview',
        routeName: 'model',
        icon: LayoutDashboard,
        disabled: true,
    },
    {
        label: 'Model card',
        routeName: 'artifact-card',
        icon: FolderDot,
        disabled: true,
    },
    {
        label: 'Experiment snapshot',
        routeName: 'experiment-snapshot',
        icon: ScanEye,
    },
]);
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['main-container']} */ ;
/** @type {__VLS_StyleScopedClasses['main-container']} */ ;
/** @type {__VLS_StyleScopedClasses['main-container']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "app-layout" },
});
/** @type {__VLS_StyleScopedClasses['app-layout']} */ ;
const __VLS_0 = LayoutHeader;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "main-container" },
});
/** @type {__VLS_StyleScopedClasses['main-container']} */ ;
const __VLS_5 = LayoutSidebar;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({}));
const __VLS_7 = __VLS_6({}, ...__VLS_functionalComponentArgsRest(__VLS_6));
__VLS_asFunctionalElement1(__VLS_intrinsics.main, __VLS_intrinsics.main)({
    ...{ class: "content-area" },
});
/** @type {__VLS_StyleScopedClasses['content-area']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content-header" },
});
/** @type {__VLS_StyleScopedClasses['content-header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "breadcrumbs" },
});
/** @type {__VLS_StyleScopedClasses['breadcrumbs']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "breadcrumb-item" },
    disabled: true,
});
/** @type {__VLS_StyleScopedClasses['breadcrumb-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "breadcrumb-separator" },
});
/** @type {__VLS_StyleScopedClasses['breadcrumb-separator']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "breadcrumb-item" },
    disabled: true,
});
/** @type {__VLS_StyleScopedClasses['breadcrumb-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "breadcrumb-separator" },
});
/** @type {__VLS_StyleScopedClasses['breadcrumb-separator']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "breadcrumb-item" },
    disabled: true,
});
/** @type {__VLS_StyleScopedClasses['breadcrumb-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({});
let __VLS_10;
/** @ts-ignore @type { | typeof __VLS_components.Tabs | typeof __VLS_components.Tabs} */
Tabs;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
    value: __VLS_ctx.$route.name,
}));
const __VLS_12 = __VLS_11({
    value: __VLS_ctx.$route.name,
}, ...__VLS_functionalComponentArgsRest(__VLS_11));
const { default: __VLS_15 } = __VLS_13.slots;
let __VLS_16;
/** @ts-ignore @type { | typeof __VLS_components.TabList | typeof __VLS_components.TabList} */
TabList;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({
    pt: (__VLS_ctx.tabsListPT),
}));
const __VLS_18 = __VLS_17({
    pt: (__VLS_ctx.tabsListPT),
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
const { default: __VLS_21 } = __VLS_19.slots;
for (const [tab] of __VLS_vFor((__VLS_ctx.items))) {
    let __VLS_22;
    /** @ts-ignore @type { | typeof __VLS_components.Tab | typeof __VLS_components.Tab} */
    Tab;
    // @ts-ignore
    const __VLS_23 = __VLS_asFunctionalComponent1(__VLS_22, new __VLS_22({
        ...{ 'onClick': {} },
        key: (tab.label),
        value: (tab.routeName),
        disabled: (tab.disabled),
        ...{ class: "tab" },
        pt: (__VLS_ctx.tabPT),
    }));
    const __VLS_24 = __VLS_23({
        ...{ 'onClick': {} },
        key: (tab.label),
        value: (tab.routeName),
        disabled: (tab.disabled),
        ...{ class: "tab" },
        pt: (__VLS_ctx.tabPT),
    }, ...__VLS_functionalComponentArgsRest(__VLS_23));
    let __VLS_27;
    const __VLS_28 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.$router.push({ name: tab.routeName });
                // @ts-ignore
                [$route, tabsListPT, items, tabPT, $router,];
            } });
    /** @type {__VLS_StyleScopedClasses['tab']} */ ;
    const { default: __VLS_29 } = __VLS_25.slots;
    const __VLS_30 = (tab.icon);
    // @ts-ignore
    const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
        size: (14),
    }));
    const __VLS_32 = __VLS_31({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_31));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (tab.label);
    // @ts-ignore
    [];
    var __VLS_25;
    var __VLS_26;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_19;
// @ts-ignore
[];
var __VLS_13;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "page-content" },
});
/** @type {__VLS_StyleScopedClasses['page-content']} */ ;
var __VLS_35 = {};
// @ts-ignore
var __VLS_36 = __VLS_35;
// @ts-ignore
[];
const __VLS_base = (await import('vue')).defineComponent({
    __typeProps: {},
});
const __VLS_export = {};
export default {};
