/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Tabs, TabList, Tab } from 'primevue';
import { Users, Orbit, FolderDot } from 'lucide-vue-next';
import { useRoute } from 'vue-router';
const tabsListPT = {
    tabList: { style: 'border-left: none; border-top: none; border-right: none;' },
};
const tabPT = {};
const items = [
    {
        label: 'Members',
        routeName: 'organization-members',
        icon: Users,
    },
    {
        label: 'Orbits',
        routeName: 'organization-orbits',
        icon: Orbit,
    },
    {
        label: 'Buckets',
        routeName: 'organization-buckets',
        icon: FolderDot,
    },
];
const route = useRoute();
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Tabs | typeof __VLS_components.Tabs} */
Tabs;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    value: __VLS_ctx.route.name,
}));
const __VLS_2 = __VLS_1({
    value: __VLS_ctx.route.name,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
let __VLS_7;
/** @ts-ignore @type { | typeof __VLS_components.TabList | typeof __VLS_components.TabList} */
TabList;
// @ts-ignore
const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
    pt: (__VLS_ctx.tabsListPT),
}));
const __VLS_9 = __VLS_8({
    pt: (__VLS_ctx.tabsListPT),
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
const { default: __VLS_12 } = __VLS_10.slots;
for (const [tab] of __VLS_vFor((__VLS_ctx.items))) {
    let __VLS_13;
    /** @ts-ignore @type { | typeof __VLS_components.Tab | typeof __VLS_components.Tab} */
    Tab;
    // @ts-ignore
    const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
        ...{ 'onClick': {} },
        pt: (__VLS_ctx.tabPT),
        key: (tab.label),
        value: (tab.routeName),
        ...{ class: "tab" },
    }));
    const __VLS_15 = __VLS_14({
        ...{ 'onClick': {} },
        pt: (__VLS_ctx.tabPT),
        key: (tab.label),
        value: (tab.routeName),
        ...{ class: "tab" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_14));
    let __VLS_18;
    const __VLS_19 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.$router.push({ name: tab.routeName });
                // @ts-ignore
                [route, tabsListPT, items, tabPT, $router,];
            } });
    /** @type {__VLS_StyleScopedClasses['tab']} */ ;
    const { default: __VLS_20 } = __VLS_16.slots;
    const __VLS_21 = (tab.icon);
    // @ts-ignore
    const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
        size: (14),
    }));
    const __VLS_23 = __VLS_22({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_22));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (tab.label);
    // @ts-ignore
    [];
    var __VLS_16;
    var __VLS_17;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_10;
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
