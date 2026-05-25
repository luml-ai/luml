/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref } from 'vue';
import { Button, Dialog, useToast } from 'primevue';
import { Trash2 } from 'lucide-vue-next';
import { useOrganizationStore } from '@/stores/organization';
import { useInvitationsStore } from '@/stores/invitations';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
const dialogPT = {
    root: {
        style: 'padding: 18px;',
    },
    header: {
        style: 'font-size: 20px; font-weight: 600; text-transform: uppercase; padding-bottom: 12px;',
    },
};
const organizationStore = useOrganizationStore();
const invitationStore = useInvitationsStore();
const toast = useToast();
const visible = ref(false);
const loading = ref(false);
const invites = computed(() => organizationStore.organizationDetails?.invites || []);
async function reject(organizationId, inviteId) {
    loading.value = true;
    try {
        await invitationStore.cancelInvite(organizationId, inviteId);
        organizationStore.removeInviteFromCurrentOrganization(inviteId);
        toast.add(simpleSuccessToast('The user is no longer invited to the organization.'));
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to remove invite'));
    }
    finally {
        loading.value = false;
    }
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    severity: "secondary",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.visible = true;
            // @ts-ignore
            [visible,];
        } });
const { default: __VLS_7 } = __VLS_3.slots;
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    visible: (__VLS_ctx.visible),
    modal: true,
    header: "Manage invites",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}));
const __VLS_10 = __VLS_9({
    visible: (__VLS_ctx.visible),
    modal: true,
    header: "Manage invites",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
const { default: __VLS_13 } = __VLS_11.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "dialog-content" },
});
/** @type {__VLS_StyleScopedClasses['dialog-content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "dialog-text" },
});
/** @type {__VLS_StyleScopedClasses['dialog-text']} */ ;
if (__VLS_ctx.invites.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "table-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['table-wrapper']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "table" },
    });
    /** @type {__VLS_StyleScopedClasses['table']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "table-header" },
    });
    /** @type {__VLS_StyleScopedClasses['table-header']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "table-row" },
    });
    /** @type {__VLS_StyleScopedClasses['table-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "table-body" },
    });
    /** @type {__VLS_StyleScopedClasses['table-body']} */ ;
    for (const [invitation] of __VLS_vFor((__VLS_ctx.invites))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "table-row" },
        });
        /** @type {__VLS_StyleScopedClasses['table-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        (invitation.email);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        (invitation.role);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        (invitation.invited_by_user?.full_name ?? 'Unknown');
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        (new Date(invitation.created_at).toLocaleDateString());
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "buttons" },
        });
        /** @type {__VLS_StyleScopedClasses['buttons']} */ ;
        let __VLS_14;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "outlined",
            disabled: (__VLS_ctx.loading),
        }));
        const __VLS_16 = __VLS_15({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "outlined",
            disabled: (__VLS_ctx.loading),
        }, ...__VLS_functionalComponentArgsRest(__VLS_15));
        let __VLS_19;
        const __VLS_20 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.invites.length))
                        return;
                    __VLS_ctx.reject(invitation.organization_id, invitation.id);
                    // @ts-ignore
                    [visible, dialogPT, invites, invites, loading, reject,];
                } });
        const { default: __VLS_21 } = __VLS_17.slots;
        {
            const { icon: __VLS_22 } = __VLS_17.slots;
            let __VLS_23;
            /** @ts-ignore @type { | typeof __VLS_components.Trash2} */
            Trash2;
            // @ts-ignore
            const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
                size: (12),
            }));
            const __VLS_25 = __VLS_24({
                size: (12),
            }, ...__VLS_functionalComponentArgsRest(__VLS_24));
            // @ts-ignore
            [];
        }
        // @ts-ignore
        [];
        var __VLS_17;
        var __VLS_18;
        // @ts-ignore
        [];
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "placeholder" },
    });
    /** @type {__VLS_StyleScopedClasses['placeholder']} */ ;
}
// @ts-ignore
[];
var __VLS_11;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
