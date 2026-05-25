/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useOrganizationStore } from '@/stores/organization';
import UiCircleProgress from '../ui/UiCircleProgress.vue';
const organizationStore = useOrganizationStore();
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['items']} */ ;
/** @type {__VLS_StyleScopedClasses['items']} */ ;
if (__VLS_ctx.organizationStore.organizationDetails) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "limits" },
    });
    /** @type {__VLS_StyleScopedClasses['limits']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "limits-title" },
    });
    /** @type {__VLS_StyleScopedClasses['limits-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "limits-text" },
    });
    /** @type {__VLS_StyleScopedClasses['limits-text']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "items" },
    });
    /** @type {__VLS_StyleScopedClasses['items']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item" },
    });
    /** @type {__VLS_StyleScopedClasses['item']} */ ;
    const __VLS_0 = UiCircleProgress || UiCircleProgress;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        progress: (((__VLS_ctx.organizationStore.organizationDetails.total_members || 0) /
            __VLS_ctx.organizationStore.organizationDetails.members_limit) *
            100),
        ...{ class: "progress" },
    }));
    const __VLS_2 = __VLS_1({
        progress: (((__VLS_ctx.organizationStore.organizationDetails.total_members || 0) /
            __VLS_ctx.organizationStore.organizationDetails.members_limit) *
            100),
        ...{ class: "progress" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    /** @type {__VLS_StyleScopedClasses['progress']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-content" },
    });
    /** @type {__VLS_StyleScopedClasses['item-content']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-values" },
    });
    /** @type {__VLS_StyleScopedClasses['item-values']} */ ;
    (__VLS_ctx.organizationStore.organizationDetails?.members.length);
    (__VLS_ctx.organizationStore.organizationDetails.members_limit);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-label" },
    });
    /** @type {__VLS_StyleScopedClasses['item-label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item" },
    });
    /** @type {__VLS_StyleScopedClasses['item']} */ ;
    const __VLS_5 = UiCircleProgress || UiCircleProgress;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        progress: (((__VLS_ctx.organizationStore.organizationDetails.total_orbits || 0) /
            __VLS_ctx.organizationStore.organizationDetails.orbits_limit) *
            100),
        ...{ class: "progress" },
    }));
    const __VLS_7 = __VLS_6({
        progress: (((__VLS_ctx.organizationStore.organizationDetails.total_orbits || 0) /
            __VLS_ctx.organizationStore.organizationDetails.orbits_limit) *
            100),
        ...{ class: "progress" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    /** @type {__VLS_StyleScopedClasses['progress']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-content" },
    });
    /** @type {__VLS_StyleScopedClasses['item-content']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-values" },
    });
    /** @type {__VLS_StyleScopedClasses['item-values']} */ ;
    (__VLS_ctx.organizationStore.organizationDetails.total_orbits);
    (__VLS_ctx.organizationStore.organizationDetails.orbits_limit);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-label" },
    });
    /** @type {__VLS_StyleScopedClasses['item-label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item" },
    });
    /** @type {__VLS_StyleScopedClasses['item']} */ ;
    const __VLS_10 = UiCircleProgress;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        progress: (((__VLS_ctx.organizationStore.organizationDetails.total_satellites || 0) /
            __VLS_ctx.organizationStore.organizationDetails.satellites_limit) *
            100),
        ...{ class: "progress" },
    }));
    const __VLS_12 = __VLS_11({
        progress: (((__VLS_ctx.organizationStore.organizationDetails.total_satellites || 0) /
            __VLS_ctx.organizationStore.organizationDetails.satellites_limit) *
            100),
        ...{ class: "progress" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    /** @type {__VLS_StyleScopedClasses['progress']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-content" },
    });
    /** @type {__VLS_StyleScopedClasses['item-content']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-values" },
    });
    /** @type {__VLS_StyleScopedClasses['item-values']} */ ;
    (__VLS_ctx.organizationStore.organizationDetails.total_satellites);
    (__VLS_ctx.organizationStore.organizationDetails.satellites_limit);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-label" },
    });
    /** @type {__VLS_StyleScopedClasses['item-label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item" },
    });
    /** @type {__VLS_StyleScopedClasses['item']} */ ;
    const __VLS_15 = UiCircleProgress;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
        progress: (((__VLS_ctx.organizationStore.organizationDetails.total_artifacts || 0) /
            __VLS_ctx.organizationStore.organizationDetails.artifacts_limit) *
            100),
        ...{ class: "progress" },
    }));
    const __VLS_17 = __VLS_16({
        progress: (((__VLS_ctx.organizationStore.organizationDetails.total_artifacts || 0) /
            __VLS_ctx.organizationStore.organizationDetails.artifacts_limit) *
            100),
        ...{ class: "progress" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    /** @type {__VLS_StyleScopedClasses['progress']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-content" },
    });
    /** @type {__VLS_StyleScopedClasses['item-content']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-values" },
    });
    /** @type {__VLS_StyleScopedClasses['item-values']} */ ;
    (__VLS_ctx.organizationStore.organizationDetails.total_artifacts);
    (__VLS_ctx.organizationStore.organizationDetails.artifacts_limit);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-label" },
    });
    /** @type {__VLS_StyleScopedClasses['item-label']} */ ;
}
// @ts-ignore
[organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
