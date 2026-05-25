/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Github, Star } from 'lucide-vue-next';
import { computed, onBeforeMount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { SIDEBAR_SECTIONS, SIDEBAR_MENU_BOTTOM } from '@/constants/constants';
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService';
import { useWindowSize } from '@/hooks/useWindowSize';
import { useOrganizationStore } from '@/stores/organization';
import { GitHubService } from '@/lib/github/GitHubService';
import { useLayout } from '@/hooks/useLayout';
import { useOrbitsStore } from '@/stores/orbits';
import { TAB_TO_ROUTE, ROUTE_TO_TAB } from '@/constants/orbit-navigation';
const route = useRoute();
const orbitsStore = useOrbitsStore();
const { headerSizes } = useLayout();
const { width } = useWindowSize();
const organizationsStore = useOrganizationStore();
const isSidebarOpened = ref(true);
const githubStarsCount = ref(null);
const ROUTES_REQUIRING_ORG_ID = ['organization', 'collection'];
const ORBIT_ROUTES = Object.values(TAB_TO_ROUTE);
const DEPLOYMENTS_GROUP = ['orbit-deployments', 'orbit-secrets'];
const getFormattedGithubStars = computed(() => {
    if (githubStarsCount.value === null)
        return null;
    else if (githubStarsCount.value < 1000)
        return githubStarsCount.value;
    else
        return (githubStarsCount.value / 1000).toFixed() + 'K';
});
function isActive(routeName) {
    const currentRouteName = route.name;
    if (currentRouteName === 'setup') {
        const tab = route.query.tab ?? 'registry';
        return TAB_TO_ROUTE[tab] === routeName;
    }
    if (routeName === 'orbit-deployments') {
        return DEPLOYMENTS_GROUP.includes(currentRouteName);
    }
    return currentRouteName === routeName;
}
function requiresOrgId(routeName) {
    return ROUTES_REQUIRING_ORG_ID.includes(routeName);
}
function getRouteParams(routeName) {
    if (ORBIT_ROUTES.includes(routeName)) {
        const orgId = organizationsStore.currentOrganization?.id;
        const orbitId = orbitsStore.currentOrbitId;
        if (orgId && orbitId) {
            return {
                name: routeName,
                params: { organizationId: orgId, id: orbitId },
            };
        }
        return {
            name: 'setup',
            query: { tab: ROUTE_TO_TAB[routeName] },
        };
    }
    if (requiresOrgId(routeName)) {
        const orgId = organizationsStore.currentOrganization?.id;
        if (!orgId)
            return null;
        if (routeName === 'organization')
            return { name: routeName, params: { id: orgId } };
        return { name: routeName, params: { organizationId: orgId } };
    }
    return null;
}
const toggleSidebar = () => {
    isSidebarOpened.value = !isSidebarOpened.value;
};
function windowResizeHandler() {
    if (window.innerWidth < 992 && isSidebarOpened.value === true) {
        isSidebarOpened.value = false;
    }
}
function sendAnalytics(option) {
    AnalyticsService.track(AnalyticsTrackKeysEnum.side_menu_select, { option });
}
async function getGithubStarsCount() {
    try {
        githubStarsCount.value = await GitHubService.getStarsCount();
    }
    catch (e) {
        console.error(e);
    }
}
watch(width, () => {
    windowResizeHandler();
});
onBeforeMount(() => {
    getGithubStarsCount();
});
onMounted(() => {
    windowResizeHandler();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['sidebar']} */ ;
/** @type {__VLS_StyleScopedClasses['section']} */ ;
/** @type {__VLS_StyleScopedClasses['closed']} */ ;
/** @type {__VLS_StyleScopedClasses['section-label']} */ ;
/** @type {__VLS_StyleScopedClasses['closed']} */ ;
/** @type {__VLS_StyleScopedClasses['section']} */ ;
/** @type {__VLS_StyleScopedClasses['section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-divider']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
/** @type {__VLS_StyleScopedClasses['icon']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['icon']} */ ;
/** @type {__VLS_StyleScopedClasses['closed']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['toggle-width-button']} */ ;
/** @type {__VLS_StyleScopedClasses['closed']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
/** @type {__VLS_StyleScopedClasses['icon']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled']} */ ;
/** @type {__VLS_StyleScopedClasses['icon']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar']} */ ;
/** @type {__VLS_StyleScopedClasses['list']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
/** @type {__VLS_StyleScopedClasses['toggle-width-button']} */ ;
/** @type {__VLS_StyleScopedClasses['organization-button-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.aside, __VLS_intrinsics.aside)({
    id: "sidebar",
    ...{ class: "sidebar" },
    ...{ class: ({ closed: !__VLS_ctx.isSidebarOpened }) },
    ...{ style: ({ paddingTop: __VLS_ctx.headerSizes.height + 32 + 'px' }) },
});
/** @type {__VLS_StyleScopedClasses['sidebar']} */ ;
/** @type {__VLS_StyleScopedClasses['closed']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.nav, __VLS_intrinsics.nav)({
    ...{ class: "nav" },
});
/** @type {__VLS_StyleScopedClasses['nav']} */ ;
for (const [section] of __VLS_vFor((__VLS_ctx.SIDEBAR_SECTIONS))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (section.id),
        ...{ class: "section" },
    });
    /** @type {__VLS_StyleScopedClasses['section']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "section-label" },
    });
    /** @type {__VLS_StyleScopedClasses['section-label']} */ ;
    (section.label);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
        ...{ class: "section-divider" },
        'aria-hidden': "true",
    });
    /** @type {__VLS_StyleScopedClasses['section-divider']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
        ...{ class: "list" },
    });
    /** @type {__VLS_StyleScopedClasses['list']} */ ;
    for (const [item] of __VLS_vFor((section.items))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
            key: (item.id),
            ...{ class: "item" },
        });
        /** @type {__VLS_StyleScopedClasses['item']} */ ;
        if (item.disabled) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "menu-link disabled" },
            });
            __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { bottom: true, }, value: (__VLS_ctx.isSidebarOpened ? item.tooltipMessage : null) }, null, null);
            __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { right: true, }, value: (!__VLS_ctx.isSidebarOpened ? item.tooltipMessage : null) }, null, null);
            /** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
            /** @type {__VLS_StyleScopedClasses['disabled']} */ ;
            const __VLS_0 = (item.icon);
            // @ts-ignore
            const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
                size: (14),
                ...{ class: "icon" },
            }));
            const __VLS_2 = __VLS_1({
                size: (14),
                ...{ class: "icon" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_1));
            /** @type {__VLS_StyleScopedClasses['icon']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (item.label);
        }
        else if (__VLS_ctx.getRouteParams(item.route)) {
            let __VLS_5;
            /** @ts-ignore @type { | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link'] | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link']} */
            routerLink;
            // @ts-ignore
            const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
                ...{ 'onClick': {} },
                to: (__VLS_ctx.getRouteParams(item.route)),
                ...{ class: "menu-link" },
                ...{ class: ({ active: __VLS_ctx.isActive(item.route) }) },
            }));
            const __VLS_7 = __VLS_6({
                ...{ 'onClick': {} },
                to: (__VLS_ctx.getRouteParams(item.route)),
                ...{ class: "menu-link" },
                ...{ class: ({ active: __VLS_ctx.isActive(item.route) }) },
            }, ...__VLS_functionalComponentArgsRest(__VLS_6));
            let __VLS_10;
            const __VLS_11 = ({ click: {} },
                { onClick: (...[$event]) => {
                        if (!!(item.disabled))
                            return;
                        if (!(__VLS_ctx.getRouteParams(item.route)))
                            return;
                        __VLS_ctx.sendAnalytics(item.analyticsOption);
                        // @ts-ignore
                        [isSidebarOpened, isSidebarOpened, isSidebarOpened, headerSizes, SIDEBAR_SECTIONS, vTooltip, vTooltip, getRouteParams, getRouteParams, isActive, sendAnalytics,];
                    } });
            /** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
            /** @type {__VLS_StyleScopedClasses['active']} */ ;
            const { default: __VLS_12 } = __VLS_8.slots;
            const __VLS_13 = (item.icon);
            // @ts-ignore
            const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
                size: (14),
                ...{ class: "icon" },
            }));
            const __VLS_15 = __VLS_14({
                size: (14),
                ...{ class: "icon" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_14));
            /** @type {__VLS_StyleScopedClasses['icon']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (item.label);
            // @ts-ignore
            [];
            var __VLS_8;
            var __VLS_9;
        }
        else {
            let __VLS_18;
            /** @ts-ignore @type { | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link'] | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link']} */
            routerLink;
            // @ts-ignore
            const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
                ...{ 'onClick': {} },
                to: ({ name: item.route }),
                ...{ class: "menu-link" },
                ...{ class: ({ active: __VLS_ctx.isActive(item.route) }) },
            }));
            const __VLS_20 = __VLS_19({
                ...{ 'onClick': {} },
                to: ({ name: item.route }),
                ...{ class: "menu-link" },
                ...{ class: ({ active: __VLS_ctx.isActive(item.route) }) },
            }, ...__VLS_functionalComponentArgsRest(__VLS_19));
            let __VLS_23;
            const __VLS_24 = ({ click: {} },
                { onClick: (...[$event]) => {
                        if (!!(item.disabled))
                            return;
                        if (!!(__VLS_ctx.getRouteParams(item.route)))
                            return;
                        __VLS_ctx.sendAnalytics(item.analyticsOption);
                        // @ts-ignore
                        [isActive, sendAnalytics,];
                    } });
            /** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
            /** @type {__VLS_StyleScopedClasses['active']} */ ;
            const { default: __VLS_25 } = __VLS_21.slots;
            const __VLS_26 = (item.icon);
            // @ts-ignore
            const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
                size: (14),
                ...{ class: "icon" },
            }));
            const __VLS_28 = __VLS_27({
                size: (14),
                ...{ class: "icon" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_27));
            /** @type {__VLS_StyleScopedClasses['icon']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (item.label);
            // @ts-ignore
            [];
            var __VLS_21;
            var __VLS_22;
        }
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sidebar-bottom" },
});
/** @type {__VLS_StyleScopedClasses['sidebar-bottom']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.nav, __VLS_intrinsics.nav)({
    ...{ class: "nav-bottom" },
});
/** @type {__VLS_StyleScopedClasses['nav-bottom']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
    ...{ class: "list" },
});
/** @type {__VLS_StyleScopedClasses['list']} */ ;
for (const [item] of __VLS_vFor((__VLS_ctx.SIDEBAR_MENU_BOTTOM))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        key: (item.id),
        ...{ class: "item" },
    });
    /** @type {__VLS_StyleScopedClasses['item']} */ ;
    if (item.link) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
            href: (item.link),
            target: "_blank",
            ...{ class: "menu-link" },
        });
        /** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
        const __VLS_31 = (item.icon);
        // @ts-ignore
        const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
            size: (14),
            ...{ class: "icon" },
        }));
        const __VLS_33 = __VLS_32({
            size: (14),
            ...{ class: "icon" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_32));
        /** @type {__VLS_StyleScopedClasses['icon']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (item.label);
    }
    // @ts-ignore
    [SIDEBAR_MENU_BOTTOM,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
    ...{ class: "item" },
});
/** @type {__VLS_StyleScopedClasses['item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
    href: "https://github.com/Dataforce-Solutions/dataforce.studio",
    target: "_blank",
    ...{ class: "menu-link menu-link--github" },
});
/** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-link--github']} */ ;
let __VLS_36;
/** @ts-ignore @type { | typeof __VLS_components.Github | typeof __VLS_components.Github} */
Github;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent1(__VLS_36, new __VLS_36({
    size: (14),
    ...{ class: "icon" },
}));
const __VLS_38 = __VLS_37({
    size: (14),
    ...{ class: "icon" },
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
/** @type {__VLS_StyleScopedClasses['icon']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "menu-link__text" },
});
/** @type {__VLS_StyleScopedClasses['menu-link__text']} */ ;
if (__VLS_ctx.getFormattedGithubStars !== null) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "menu-link__info" },
    });
    /** @type {__VLS_StyleScopedClasses['menu-link__info']} */ ;
    let __VLS_41;
    /** @ts-ignore @type { | typeof __VLS_components.Star} */
    Star;
    // @ts-ignore
    const __VLS_42 = __VLS_asFunctionalComponent1(__VLS_41, new __VLS_41({
        size: (10),
    }));
    const __VLS_43 = __VLS_42({
        size: (10),
    }, ...__VLS_functionalComponentArgsRest(__VLS_42));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (__VLS_ctx.getFormattedGithubStars);
}
let __VLS_46;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_47 = __VLS_asFunctionalComponent1(__VLS_46, new __VLS_46({
    ...{ 'onClick': {} },
    severity: "contrast",
    variant: "text",
    rounded: true,
    ...{ class: "toggle-width-button" },
    ...{ class: ({ closed: !__VLS_ctx.isSidebarOpened }) },
}));
const __VLS_48 = __VLS_47({
    ...{ 'onClick': {} },
    severity: "contrast",
    variant: "text",
    rounded: true,
    ...{ class: "toggle-width-button" },
    ...{ class: ({ closed: !__VLS_ctx.isSidebarOpened }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_47));
let __VLS_51;
const __VLS_52 = ({ click: {} },
    { onClick: (__VLS_ctx.toggleSidebar) });
/** @type {__VLS_StyleScopedClasses['toggle-width-button']} */ ;
/** @type {__VLS_StyleScopedClasses['closed']} */ ;
const { default: __VLS_53 } = __VLS_49.slots;
{
    const { icon: __VLS_54 } = __VLS_49.slots;
    let __VLS_55;
    /** @ts-ignore @type { | typeof __VLS_components.arrowLeftToLine | typeof __VLS_components.ArrowLeftToLine | typeof __VLS_components['arrow-left-to-line']} */
    arrowLeftToLine;
    // @ts-ignore
    const __VLS_56 = __VLS_asFunctionalComponent1(__VLS_55, new __VLS_55({
        size: (14),
        color: "var(--p-button-text-plain-color)",
    }));
    const __VLS_57 = __VLS_56({
        size: (14),
        color: "var(--p-button-text-plain-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_56));
    // @ts-ignore
    [isSidebarOpened, getFormattedGithubStars, getFormattedGithubStars, toggleSidebar,];
}
// @ts-ignore
[];
var __VLS_49;
var __VLS_50;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
