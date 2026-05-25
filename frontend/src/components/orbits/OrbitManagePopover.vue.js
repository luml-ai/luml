/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref } from 'vue';
import { Orbit, ChevronDown, Plus, Bolt } from 'lucide-vue-next';
import { Popover } from 'primevue';
import { useOrbitsStore } from '@/stores/orbits';
import { useOrganizationStore } from '@/stores/organization';
import { PermissionEnum } from '@/lib/api/api.interfaces';
import OrbitCreator from './creator/OrbitCreator.vue';
import UiId from '@/components/ui/UiId.vue';
import OrbitEditor from './editor/OrbitEditor.vue';
import { useRouter, useRoute } from 'vue-router';
import { ROUTE_TO_TAB, TAB_TO_ROUTE } from '@/constants/orbit-navigation';
const router = useRouter();
const route = useRoute();
const orbitsStore = useOrbitsStore();
const organizationStore = useOrganizationStore();
const isSettingsMode = ref(false);
const popover = ref();
const isCreateMode = ref(false);
const isOrbitLimitReached = computed(() => {
    const details = organizationStore.organizationDetails;
    if (!details)
        return true;
    return details.total_orbits >= details.orbits_limit;
});
const createAvailable = computed(() => organizationStore.currentOrganization?.permissions?.orbit?.includes(PermissionEnum.create) ??
    false);
function toggle(event) {
    popover.value.toggle(event);
}
async function onOrbitClick(orbitId) {
    const orgId = organizationStore.currentOrganization?.id;
    if (!orgId)
        return;
    const currentName = route.name;
    const isOnOrbitRoute = !!route.params.organizationId && !!route.params.id;
    if (isOnOrbitRoute) {
        const tab = ROUTE_TO_TAB[currentName] ?? 'registry';
        const targetRoute = TAB_TO_ROUTE[tab] ?? 'orbit-registry';
        await router.push({
            name: targetRoute,
            params: { organizationId: orgId, id: orbitId },
        });
    }
    else {
        orbitsStore.setCurrentOrbitId(orbitId, orgId);
    }
    popover.value.hide();
}
function onSettingsClick() {
    popover.value.hide();
    isSettingsMode.value = true;
}
function onCreateClick() {
    popover.value.hide();
    isCreateMode.value = true;
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['menu-item']} */ ;
/** @type {__VLS_StyleScopedClasses['menu-item']} */ ;
/** @type {__VLS_StyleScopedClasses['orbit-item']} */ ;
/** @type {__VLS_StyleScopedClasses['p-popover']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "orbit-popover-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['orbit-popover-wrapper']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    variant: "text",
    ...{ class: "menu-link" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    variant: "text",
    ...{ class: "menu-link" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (__VLS_ctx.toggle) });
/** @type {__VLS_StyleScopedClasses['menu-link']} */ ;
const { default: __VLS_7 } = __VLS_3.slots;
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.Orbit} */
Orbit;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    size: (14),
    ...{ class: "icon" },
}));
const __VLS_10 = __VLS_9({
    size: (14),
    ...{ class: "icon" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
/** @type {__VLS_StyleScopedClasses['icon']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
(__VLS_ctx.orbitsStore.currentOrbit?.name ?? 'Orbit');
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.ChevronDown} */
ChevronDown;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    size: (20),
    ...{ class: "icon" },
}));
const __VLS_15 = __VLS_14({
    size: (20),
    ...{ class: "icon" },
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
/** @type {__VLS_StyleScopedClasses['icon']} */ ;
// @ts-ignore
[toggle, orbitsStore,];
var __VLS_3;
var __VLS_4;
let __VLS_18;
/** @ts-ignore @type { | typeof __VLS_components.Popover | typeof __VLS_components.Popover} */
Popover;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
    ref: "popover",
    appendTo: "self",
    ...{ class: "popover-without-arrow" },
    ...{ style: {} },
}));
const __VLS_20 = __VLS_19({
    ref: "popover",
    appendTo: "self",
    ...{ class: "popover-without-arrow" },
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_19));
var __VLS_23;
/** @type {__VLS_StyleScopedClasses['popover-without-arrow']} */ ;
const { default: __VLS_25 } = __VLS_21.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-content" },
});
/** @type {__VLS_StyleScopedClasses['popover-content']} */ ;
if (__VLS_ctx.orbitsStore.currentOrbit) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
        ...{ class: "header" },
    });
    /** @type {__VLS_StyleScopedClasses['header']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "header-content" },
    });
    /** @type {__VLS_StyleScopedClasses['header-content']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "name" },
    });
    /** @type {__VLS_StyleScopedClasses['name']} */ ;
    (__VLS_ctx.orbitsStore.currentOrbit.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "meta-row" },
    });
    /** @type {__VLS_StyleScopedClasses['meta-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "collections-count" },
    });
    /** @type {__VLS_StyleScopedClasses['collections-count']} */ ;
    (__VLS_ctx.orbitsStore.currentOrbitDetails?.total_collections ?? 0);
    if (__VLS_ctx.orbitsStore.currentOrbit.id) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "id-row" },
        });
        /** @type {__VLS_StyleScopedClasses['id-row']} */ ;
        const __VLS_26 = UiId;
        // @ts-ignore
        const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
            id: (__VLS_ctx.orbitsStore.currentOrbit.id),
            ...{ class: "id-value" },
        }));
        const __VLS_28 = __VLS_27({
            id: (__VLS_ctx.orbitsStore.currentOrbit.id),
            ...{ class: "id-value" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_27));
        /** @type {__VLS_StyleScopedClasses['id-value']} */ ;
    }
}
if (__VLS_ctx.orbitsStore.orbitsList.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "popover-label" },
    });
    /** @type {__VLS_StyleScopedClasses['popover-label']} */ ;
}
if (__VLS_ctx.orbitsStore.orbitsList.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "list-scroll" },
    });
    /** @type {__VLS_StyleScopedClasses['list-scroll']} */ ;
    for (const [orbit] of __VLS_vFor((__VLS_ctx.orbitsStore.orbitsList))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (orbit.id),
            ...{ class: "orbit-item" },
            ...{ class: ({ active: orbit.id === __VLS_ctx.orbitsStore.currentOrbit?.id }) },
        });
        /** @type {__VLS_StyleScopedClasses['orbit-item']} */ ;
        /** @type {__VLS_StyleScopedClasses['active']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.orbitsStore.orbitsList.length))
                        return;
                    __VLS_ctx.onOrbitClick(orbit.id);
                    // @ts-ignore
                    [orbitsStore, orbitsStore, orbitsStore, orbitsStore, orbitsStore, orbitsStore, orbitsStore, orbitsStore, orbitsStore, onOrbitClick,];
                } },
            ...{ class: "menu-item" },
        });
        /** @type {__VLS_StyleScopedClasses['menu-item']} */ ;
        (orbit.name);
        if (orbit.id === __VLS_ctx.orbitsStore.currentOrbit?.id &&
            __VLS_ctx.orbitsStore.currentOrbitDetails?.permissions?.orbit?.includes(__VLS_ctx.PermissionEnum.update)) {
            let __VLS_31;
            /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
            dButton;
            // @ts-ignore
            const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
                ...{ 'onClick': {} },
                variant: "text",
                severity: "secondary",
                size: "small",
            }));
            const __VLS_33 = __VLS_32({
                ...{ 'onClick': {} },
                variant: "text",
                severity: "secondary",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_32));
            let __VLS_36;
            const __VLS_37 = ({ click: {} },
                { onClick: (__VLS_ctx.onSettingsClick) });
            const { default: __VLS_38 } = __VLS_34.slots;
            {
                const { icon: __VLS_39 } = __VLS_34.slots;
                let __VLS_40;
                /** @ts-ignore @type { | typeof __VLS_components.Bolt} */
                Bolt;
                // @ts-ignore
                const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
                    size: (14),
                }));
                const __VLS_42 = __VLS_41({
                    size: (14),
                }, ...__VLS_functionalComponentArgsRest(__VLS_41));
                // @ts-ignore
                [orbitsStore, orbitsStore, PermissionEnum, onSettingsClick,];
            }
            // @ts-ignore
            [];
            var __VLS_34;
            var __VLS_35;
        }
        // @ts-ignore
        [];
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "empty" },
    });
    /** @type {__VLS_StyleScopedClasses['empty']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "empty-text-header" },
    });
    /** @type {__VLS_StyleScopedClasses['empty-text-header']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "empty-text" },
    });
    /** @type {__VLS_StyleScopedClasses['empty-text']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.footer, __VLS_intrinsics.footer)({
    ...{ class: "footer" },
});
/** @type {__VLS_StyleScopedClasses['footer']} */ ;
if (__VLS_ctx.createAvailable) {
    let __VLS_45;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({
        ...{ 'onClick': {} },
        severity: "secondary",
        disabled: (__VLS_ctx.isOrbitLimitReached),
        ...{ class: "create-button" },
    }));
    const __VLS_47 = __VLS_46({
        ...{ 'onClick': {} },
        severity: "secondary",
        disabled: (__VLS_ctx.isOrbitLimitReached),
        ...{ class: "create-button" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_46));
    let __VLS_50;
    const __VLS_51 = ({ click: {} },
        { onClick: (__VLS_ctx.onCreateClick) });
    __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { top: true, }, value: (__VLS_ctx.isOrbitLimitReached ? 'Orbit limit reached for this organization' : null) }, null, null);
    /** @type {__VLS_StyleScopedClasses['create-button']} */ ;
    const { default: __VLS_52 } = __VLS_48.slots;
    let __VLS_53;
    /** @ts-ignore @type { | typeof __VLS_components.Plus} */
    Plus;
    // @ts-ignore
    const __VLS_54 = __VLS_asFunctionalComponent1(__VLS_53, new __VLS_53({
        size: (14),
    }));
    const __VLS_55 = __VLS_54({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_54));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [createAvailable, isOrbitLimitReached, isOrbitLimitReached, onCreateClick, vTooltip,];
    var __VLS_48;
    var __VLS_49;
}
// @ts-ignore
[];
var __VLS_21;
if (__VLS_ctx.organizationStore.currentOrganization) {
    const __VLS_58 = OrbitCreator;
    // @ts-ignore
    const __VLS_59 = __VLS_asFunctionalComponent1(__VLS_58, new __VLS_58({
        visible: (__VLS_ctx.isCreateMode),
        organizationId: (__VLS_ctx.organizationStore.currentOrganization.id),
    }));
    const __VLS_60 = __VLS_59({
        visible: (__VLS_ctx.isCreateMode),
        organizationId: (__VLS_ctx.organizationStore.currentOrganization.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_59));
}
if (__VLS_ctx.orbitsStore.currentOrbitDetails) {
    const __VLS_63 = OrbitEditor;
    // @ts-ignore
    const __VLS_64 = __VLS_asFunctionalComponent1(__VLS_63, new __VLS_63({
        visible: (__VLS_ctx.isSettingsMode),
        orbit: (__VLS_ctx.orbitsStore.currentOrbitDetails),
    }));
    const __VLS_65 = __VLS_64({
        visible: (__VLS_ctx.isSettingsMode),
        orbit: (__VLS_ctx.orbitsStore.currentOrbitDetails),
    }, ...__VLS_functionalComponentArgsRest(__VLS_64));
}
// @ts-ignore
var __VLS_24 = __VLS_23;
// @ts-ignore
[orbitsStore, orbitsStore, organizationStore, organizationStore, isCreateMode, isSettingsMode,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
