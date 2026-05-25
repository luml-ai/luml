/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref } from 'vue';
import { Users, ChevronDown, Plus, Bolt } from 'lucide-vue-next';
import { Popover, Avatar, Dialog } from 'primevue';
import { useOrganizationStore } from '@/stores/organization';
import { useOrbitsStore } from '@/stores/orbits';
import OrganizationCreator from './OrganizationCreator.vue';
import OrganizationLeavePopover from './OrganizationLeavePopover.vue';
import UiId from '../ui/UiId.vue';
import { PermissionEnum } from '@/lib/api/api.interfaces';
import { useRouter, useRoute } from 'vue-router';
import { ROUTE_TO_TAB, TAB_TO_ROUTE } from '@/constants/orbit-navigation';
const router = useRouter();
const route = useRoute();
const organizationStore = useOrganizationStore();
const orbitsStore = useOrbitsStore();
const popover = ref();
const isCreateMode = ref(false);
const isSettingsDisabled = computed(() => !organizationStore.currentOrganization?.permissions?.organization?.includes(PermissionEnum.read));
const currentOrganizationAvatarLabel = computed(() => organizationStore.currentOrganization?.name.charAt(0).toUpperCase());
function toggle(event) {
    popover.value.toggle(event);
}
function onCreateClick() {
    popover.value.hide();
    isCreateMode.value = true;
}
async function onOrganizationClick(organizationId) {
    await organizationStore.switchOrganization(organizationId);
    const currentName = route.name;
    const isOnOrgPage = route.matched.some((r) => r.name === 'organization');
    const hasOrgInUrl = !!route.params.organizationId;
    if (isOnOrgPage) {
        await router.push({
            name: currentName,
            params: { id: organizationId },
        });
    }
    else if (hasOrgInUrl) {
        const firstOrbit = orbitsStore.orbitsList[0];
        const tab = ROUTE_TO_TAB[currentName] ?? 'registry';
        const targetRoute = TAB_TO_ROUTE[tab] ?? 'orbit-registry';
        if (firstOrbit) {
            await router.push({
                name: targetRoute,
                params: { organizationId, id: firstOrbit.id },
            });
        }
        else {
            await router.push({ name: 'setup', query: { tab } });
        }
    }
    popover.value.hide();
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
/** @type {__VLS_StyleScopedClasses['p-popover']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "org-popover-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['org-popover-wrapper']} */ ;
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
/** @ts-ignore @type { | typeof __VLS_components.Users | typeof __VLS_components.Users} */
Users;
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
(__VLS_ctx.organizationStore.currentOrganization?.name);
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
[toggle, organizationStore,];
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
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
let __VLS_26;
/** @ts-ignore @type { | typeof __VLS_components.Avatar} */
Avatar;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
    size: "large",
    label: (__VLS_ctx.currentOrganizationAvatarLabel),
}));
const __VLS_28 = __VLS_27({
    size: "large",
    label: (__VLS_ctx.currentOrganizationAvatarLabel),
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "header-content" },
});
/** @type {__VLS_StyleScopedClasses['header-content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "name" },
});
/** @type {__VLS_StyleScopedClasses['name']} */ ;
(__VLS_ctx.organizationStore.currentOrganization?.name);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "members-row" },
});
/** @type {__VLS_StyleScopedClasses['members-row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "members" },
});
/** @type {__VLS_StyleScopedClasses['members']} */ ;
(__VLS_ctx.organizationStore.currentOrganization?.members_count);
if (__VLS_ctx.organizationStore.currentOrganization?.id) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "id-row" },
    });
    /** @type {__VLS_StyleScopedClasses['id-row']} */ ;
    const __VLS_31 = UiId || UiId;
    // @ts-ignore
    const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
        id: (__VLS_ctx.organizationStore.currentOrganization.id),
        ...{ class: "id-value" },
    }));
    const __VLS_33 = __VLS_32({
        id: (__VLS_ctx.organizationStore.currentOrganization.id),
        ...{ class: "id-value" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_32));
    /** @type {__VLS_StyleScopedClasses['id-value']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-label" },
});
/** @type {__VLS_StyleScopedClasses['popover-label']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "list-scroll" },
});
/** @type {__VLS_StyleScopedClasses['list-scroll']} */ ;
for (const [organization] of __VLS_vFor((__VLS_ctx.organizationStore.availableOrganizations))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "organization" },
        ...{ class: ({ active: organization.id === __VLS_ctx.organizationStore.currentOrganization?.id }) },
    });
    /** @type {__VLS_StyleScopedClasses['organization']} */ ;
    /** @type {__VLS_StyleScopedClasses['active']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.onOrganizationClick(organization.id);
                // @ts-ignore
                [organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, organizationStore, currentOrganizationAvatarLabel, onOrganizationClick,];
            } },
        ...{ class: "menu-item" },
    });
    /** @type {__VLS_StyleScopedClasses['menu-item']} */ ;
    (organization.name);
    if (organization.permissions?.organization?.includes(__VLS_ctx.PermissionEnum.leave)) {
        const __VLS_36 = OrganizationLeavePopover;
        // @ts-ignore
        const __VLS_37 = __VLS_asFunctionalComponent1(__VLS_36, new __VLS_36({
            organizationId: (organization.id),
        }));
        const __VLS_38 = __VLS_37({
            organizationId: (organization.id),
        }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    }
    // @ts-ignore
    [PermissionEnum,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.footer, __VLS_intrinsics.footer)({
    ...{ class: "footer" },
});
/** @type {__VLS_StyleScopedClasses['footer']} */ ;
let __VLS_41;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_42 = __VLS_asFunctionalComponent1(__VLS_41, new __VLS_41({
    ...{ 'onClick': {} },
    severity: "secondary",
}));
const __VLS_43 = __VLS_42({
    ...{ 'onClick': {} },
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_42));
let __VLS_46;
const __VLS_47 = ({ click: {} },
    { onClick: (__VLS_ctx.onCreateClick) });
const { default: __VLS_48 } = __VLS_44.slots;
let __VLS_49;
/** @ts-ignore @type { | typeof __VLS_components.Plus} */
Plus;
// @ts-ignore
const __VLS_50 = __VLS_asFunctionalComponent1(__VLS_49, new __VLS_49({
    size: (14),
}));
const __VLS_51 = __VLS_50({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_50));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
// @ts-ignore
[onCreateClick,];
var __VLS_44;
var __VLS_45;
if (__VLS_ctx.organizationStore.currentOrganization) {
    let __VLS_54;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_55 = __VLS_asFunctionalComponent1(__VLS_54, new __VLS_54({
        asChild: true,
        variant: "outlined",
        severity: "secondary",
        disabled: (__VLS_ctx.isSettingsDisabled),
    }));
    const __VLS_56 = __VLS_55({
        asChild: true,
        variant: "outlined",
        severity: "secondary",
        disabled: (__VLS_ctx.isSettingsDisabled),
    }, ...__VLS_functionalComponentArgsRest(__VLS_55));
    {
        const { default: __VLS_59 } = __VLS_57.slots;
        const [slotProps] = __VLS_vSlot(__VLS_59);
        if (__VLS_ctx.isSettingsDisabled) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                ...{ class: (slotProps.class) },
                disabled: true,
            });
            let __VLS_60;
            /** @ts-ignore @type { | typeof __VLS_components.Bolt} */
            Bolt;
            // @ts-ignore
            const __VLS_61 = __VLS_asFunctionalComponent1(__VLS_60, new __VLS_60({
                size: (14),
            }));
            const __VLS_62 = __VLS_61({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_61));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        }
        else {
            let __VLS_65;
            /** @ts-ignore @type { | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link'] | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link']} */
            routerLink;
            // @ts-ignore
            const __VLS_66 = __VLS_asFunctionalComponent1(__VLS_65, new __VLS_65({
                ...{ 'onClick': {} },
                to: ({
                    name: 'organization-members',
                    params: { id: __VLS_ctx.organizationStore.currentOrganization.id },
                }),
                ...{ class: (slotProps.class) },
            }));
            const __VLS_67 = __VLS_66({
                ...{ 'onClick': {} },
                to: ({
                    name: 'organization-members',
                    params: { id: __VLS_ctx.organizationStore.currentOrganization.id },
                }),
                ...{ class: (slotProps.class) },
            }, ...__VLS_functionalComponentArgsRest(__VLS_66));
            let __VLS_70;
            const __VLS_71 = ({ click: {} },
                { onClick: (__VLS_ctx.toggle) });
            const { default: __VLS_72 } = __VLS_68.slots;
            let __VLS_73;
            /** @ts-ignore @type { | typeof __VLS_components.Bolt} */
            Bolt;
            // @ts-ignore
            const __VLS_74 = __VLS_asFunctionalComponent1(__VLS_73, new __VLS_73({
                size: (14),
            }));
            const __VLS_75 = __VLS_74({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_74));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            // @ts-ignore
            [toggle, organizationStore, organizationStore, isSettingsDisabled, isSettingsDisabled,];
            var __VLS_68;
            var __VLS_69;
        }
        // @ts-ignore
        [];
        __VLS_57.slots['' /* empty slot name completion */];
    }
    var __VLS_57;
}
// @ts-ignore
[];
var __VLS_21;
let __VLS_78;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_79 = __VLS_asFunctionalComponent1(__VLS_78, new __VLS_78({
    visible: (__VLS_ctx.isCreateMode),
    modal: true,
    draggable: (false),
    ...{ style: {} },
}));
const __VLS_80 = __VLS_79({
    visible: (__VLS_ctx.isCreateMode),
    modal: true,
    draggable: (false),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_79));
const { default: __VLS_83 } = __VLS_81.slots;
{
    const { header: __VLS_84 } = __VLS_81.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "creator-title" },
    });
    /** @type {__VLS_StyleScopedClasses['creator-title']} */ ;
    // @ts-ignore
    [isCreateMode,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "creator-text" },
});
/** @type {__VLS_StyleScopedClasses['creator-text']} */ ;
const __VLS_85 = OrganizationCreator || OrganizationCreator;
// @ts-ignore
const __VLS_86 = __VLS_asFunctionalComponent1(__VLS_85, new __VLS_85({
    ...{ 'onClose': {} },
}));
const __VLS_87 = __VLS_86({
    ...{ 'onClose': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_86));
let __VLS_90;
const __VLS_91 = ({ close: {} },
    { onClose: (...[$event]) => {
            __VLS_ctx.isCreateMode = false;
            // @ts-ignore
            [isCreateMode,];
        } });
var __VLS_88;
var __VLS_89;
// @ts-ignore
[];
var __VLS_81;
// @ts-ignore
var __VLS_24 = __VLS_23;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
