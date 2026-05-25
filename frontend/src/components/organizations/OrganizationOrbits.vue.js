/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useOrganizationStore } from '@/stores/organization';
import { Button } from 'primevue';
import { Plus } from 'lucide-vue-next';
import { PermissionEnum } from '@/lib/api/api.interfaces';
import { computed, ref } from 'vue';
import OrganizationOrbitSettings from './OrganizationOrbitSettings.vue';
import OrbitCreator from '../orbits/creator/OrbitCreator.vue';
const organizationStore = useOrganizationStore();
const showCreator = ref(false);
const createAvailable = computed(() => {
    return !!organizationStore.currentOrganization?.permissions?.orbit?.includes(PermissionEnum.create);
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar" },
});
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
(__VLS_ctx.organizationStore.organizationDetails?.orbits.length || 0);
if (__VLS_ctx.createAvailable) {
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onClick': {} },
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.createAvailable))
                    return;
                __VLS_ctx.showCreator = true;
                // @ts-ignore
                [organizationStore, createAvailable, showCreator,];
            } });
    const { default: __VLS_7 } = __VLS_3.slots;
    let __VLS_8;
    /** @ts-ignore @type { | typeof __VLS_components.Plus} */
    Plus;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        size: (14),
    }));
    const __VLS_10 = __VLS_9({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [];
    var __VLS_3;
    var __VLS_4;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "users-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['users-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "users" },
});
/** @type {__VLS_StyleScopedClasses['users']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "users-header" },
});
/** @type {__VLS_StyleScopedClasses['users-header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "row" },
});
/** @type {__VLS_StyleScopedClasses['row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "cell" },
});
/** @type {__VLS_StyleScopedClasses['cell']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "cell" },
});
/** @type {__VLS_StyleScopedClasses['cell']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "cell" },
});
/** @type {__VLS_StyleScopedClasses['cell']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "cell" },
});
/** @type {__VLS_StyleScopedClasses['cell']} */ ;
if (__VLS_ctx.organizationStore.organizationDetails?.orbits.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "users-list" },
    });
    /** @type {__VLS_StyleScopedClasses['users-list']} */ ;
    for (const [orbit] of __VLS_vFor((__VLS_ctx.organizationStore.organizationDetails.orbits))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "row" },
        });
        /** @type {__VLS_StyleScopedClasses['row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell cell-user" },
            ...{ style: {} },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        /** @type {__VLS_StyleScopedClasses['cell-user']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
            ...{ style: {} },
        });
        (orbit.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        (orbit.total_members);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        (new Date(orbit.created_at).toLocaleDateString());
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        const __VLS_13 = OrganizationOrbitSettings || OrganizationOrbitSettings;
        // @ts-ignore
        const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
            orbitId: (orbit.id),
        }));
        const __VLS_15 = __VLS_14({
            orbitId: (orbit.id),
        }, ...__VLS_functionalComponentArgsRest(__VLS_14));
        // @ts-ignore
        [organizationStore, organizationStore,];
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
}
if (__VLS_ctx.organizationStore.currentOrganization) {
    const __VLS_18 = OrbitCreator || OrbitCreator;
    // @ts-ignore
    const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
        visible: (__VLS_ctx.showCreator),
        organizationId: (__VLS_ctx.organizationStore.currentOrganization.id),
    }));
    const __VLS_20 = __VLS_19({
        visible: (__VLS_ctx.showCreator),
        organizationId: (__VLS_ctx.organizationStore.currentOrganization.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_19));
}
// @ts-ignore
[organizationStore, organizationStore, showCreator,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
