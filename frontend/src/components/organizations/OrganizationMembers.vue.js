/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Badge, Avatar } from 'primevue';
import { useOrganizationStore } from '@/stores/organization';
import { computed } from 'vue';
import { OrganizationRoleEnum } from './organization.interfaces';
import OrganizationUserSettings from './OrganizationUserSettings.vue';
import OrganizationCreateInvite from './OrganizationCreateInvite.vue';
import OrganizationInviteManager from './OrganizationInviteManager.vue';
import { useUserStore } from '@/stores/user';
const organizationStore = useOrganizationStore();
const userStore = useUserStore();
const members = computed(() => organizationStore.organizationDetails?.members || []);
const ownersCount = computed(() => members.value.filter((member) => member.role === OrganizationRoleEnum.owner).length);
const adminsCount = computed(() => members.value.filter((member) => member.role === OrganizationRoleEnum.admin).length);
const membersCount = computed(() => members.value.filter((member) => member.role === OrganizationRoleEnum.member).length);
const isUserOwner = computed(() => members.value.find((member) => member.user.id === userStore.getUserId)?.role ===
    OrganizationRoleEnum.owner);
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['list']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
(__VLS_ctx.members.length);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar" },
});
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "buttons" },
});
/** @type {__VLS_StyleScopedClasses['buttons']} */ ;
const __VLS_0 = OrganizationCreateInvite || OrganizationCreateInvite;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const __VLS_5 = OrganizationInviteManager || OrganizationInviteManager;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({}));
const __VLS_7 = __VLS_6({}, ...__VLS_functionalComponentArgsRest(__VLS_6));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "list" },
});
/** @type {__VLS_StyleScopedClasses['list']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "item" },
});
/** @type {__VLS_StyleScopedClasses['item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "item-label" },
});
/** @type {__VLS_StyleScopedClasses['item-label']} */ ;
let __VLS_10;
/** @ts-ignore @type { | typeof __VLS_components.Badge} */
Badge;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
    value: (__VLS_ctx.ownersCount),
}));
const __VLS_12 = __VLS_11({
    value: (__VLS_ctx.ownersCount),
}, ...__VLS_functionalComponentArgsRest(__VLS_11));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "item" },
});
/** @type {__VLS_StyleScopedClasses['item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "item-label" },
});
/** @type {__VLS_StyleScopedClasses['item-label']} */ ;
let __VLS_15;
/** @ts-ignore @type { | typeof __VLS_components.Badge} */
Badge;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    value: (__VLS_ctx.adminsCount),
}));
const __VLS_17 = __VLS_16({
    value: (__VLS_ctx.adminsCount),
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "item" },
});
/** @type {__VLS_StyleScopedClasses['item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "item-label" },
});
/** @type {__VLS_StyleScopedClasses['item-label']} */ ;
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.Badge} */
Badge;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    value: (__VLS_ctx.membersCount),
}));
const __VLS_22 = __VLS_21({
    value: (__VLS_ctx.membersCount),
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "users-list" },
});
/** @type {__VLS_StyleScopedClasses['users-list']} */ ;
for (const [member] of __VLS_vFor((__VLS_ctx.members))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "row" },
    });
    /** @type {__VLS_StyleScopedClasses['row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell cell-user" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    /** @type {__VLS_StyleScopedClasses['cell-user']} */ ;
    let __VLS_25;
    /** @ts-ignore @type { | typeof __VLS_components.Avatar} */
    Avatar;
    // @ts-ignore
    const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
        label: (member.user.photo ? undefined : member.user.full_name[0]),
        shape: "circle",
        image: (member.user.photo),
    }));
    const __VLS_27 = __VLS_26({
        label: (member.user.photo ? undefined : member.user.full_name[0]),
        shape: "circle",
        image: (member.user.photo),
    }, ...__VLS_functionalComponentArgsRest(__VLS_26));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({});
    (member.user.full_name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "email" },
    });
    /** @type {__VLS_StyleScopedClasses['email']} */ ;
    (member.user.email);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    (member.role);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    (new Date(member.created_at).toLocaleDateString());
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    if (member.role === __VLS_ctx.OrganizationRoleEnum.member ||
        (member.role === __VLS_ctx.OrganizationRoleEnum.admin && __VLS_ctx.isUserOwner)) {
        const __VLS_30 = OrganizationUserSettings || OrganizationUserSettings;
        // @ts-ignore
        const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
            member: (member),
        }));
        const __VLS_32 = __VLS_31({
            member: (member),
        }, ...__VLS_functionalComponentArgsRest(__VLS_31));
    }
    // @ts-ignore
    [members, members, ownersCount, adminsCount, membersCount, OrganizationRoleEnum, OrganizationRoleEnum, isUserOwner,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
