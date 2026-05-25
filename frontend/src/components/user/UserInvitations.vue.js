/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { Bell, Trash2, Check } from 'lucide-vue-next';
import { Dialog, useToast } from 'primevue';
import { useInvitationsStore } from '@/stores/invitations';
import { simpleErrorToast, simpleSuccessToast, simpleWardToast } from '@/lib/primevue/data/toasts';
const invitationsStore = useInvitationsStore();
const toast = useToast();
const visible = ref(false);
const loading = ref(false);
async function accept(inviteId, organizationId) {
    loading.value = true;
    try {
        await invitationsStore.acceptInvitation(inviteId, organizationId);
        toast.add(simpleSuccessToast('You’ve joined the organization successfully.'));
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to accept the invitation'));
    }
    finally {
        loading.value = false;
    }
}
async function reject(inviteId) {
    loading.value = true;
    try {
        await invitationsStore.rejectInvitation(inviteId);
        toast.add(simpleWardToast('The invitation has been declined.'));
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to reject the invitation'));
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "user-notification" },
});
/** @type {__VLS_StyleScopedClasses['user-notification']} */ ;
if (__VLS_ctx.invitationsStore.invitations.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "user-notification__circle" },
    });
    /** @type {__VLS_StyleScopedClasses['user-notification__circle']} */ ;
}
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    rounded: true,
    severity: "help",
    ...{ class: "bell-button" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    rounded: true,
    severity: "help",
    ...{ class: "bell-button" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.visible = true;
            // @ts-ignore
            [invitationsStore, visible,];
        } });
/** @type {__VLS_StyleScopedClasses['bell-button']} */ ;
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { icon: __VLS_8 } = __VLS_3.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.Bell} */
    Bell;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        size: (12),
    }));
    const __VLS_11 = __VLS_10({
        size: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
let __VLS_14;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
    visible: (__VLS_ctx.visible),
    modal: true,
    draggable: (false),
    ...{ style: ({ maxWidth: '1000px', width: '100%', padding: '18px' }) },
}));
const __VLS_16 = __VLS_15({
    visible: (__VLS_ctx.visible),
    modal: true,
    draggable: (false),
    ...{ style: ({ maxWidth: '1000px', width: '100%', padding: '18px' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
const { default: __VLS_19 } = __VLS_17.slots;
{
    const { header: __VLS_20 } = __VLS_17.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "title" },
    });
    /** @type {__VLS_StyleScopedClasses['title']} */ ;
    // @ts-ignore
    [visible,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
    ...{ class: "sub-title" },
});
/** @type {__VLS_StyleScopedClasses['sub-title']} */ ;
if (__VLS_ctx.invitationsStore.invitations.length) {
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
    for (const [invitation] of __VLS_vFor((__VLS_ctx.invitationsStore.invitations))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "table-row" },
        });
        /** @type {__VLS_StyleScopedClasses['table-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        (invitation.organization.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        (invitation.role);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        (invitation.invited_by_user.full_name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        (new Date(invitation.created_at).toLocaleDateString());
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "buttons" },
        });
        /** @type {__VLS_StyleScopedClasses['buttons']} */ ;
        let __VLS_21;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "outlined",
            disabled: (__VLS_ctx.loading),
        }));
        const __VLS_23 = __VLS_22({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "outlined",
            disabled: (__VLS_ctx.loading),
        }, ...__VLS_functionalComponentArgsRest(__VLS_22));
        let __VLS_26;
        const __VLS_27 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.invitationsStore.invitations.length))
                        return;
                    __VLS_ctx.reject(invitation.id);
                    // @ts-ignore
                    [invitationsStore, invitationsStore, loading, reject,];
                } });
        const { default: __VLS_28 } = __VLS_24.slots;
        {
            const { icon: __VLS_29 } = __VLS_24.slots;
            let __VLS_30;
            /** @ts-ignore @type { | typeof __VLS_components.Trash2} */
            Trash2;
            // @ts-ignore
            const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
                size: (12),
            }));
            const __VLS_32 = __VLS_31({
                size: (12),
            }, ...__VLS_functionalComponentArgsRest(__VLS_31));
            // @ts-ignore
            [];
        }
        // @ts-ignore
        [];
        var __VLS_24;
        var __VLS_25;
        let __VLS_35;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_36 = __VLS_asFunctionalComponent1(__VLS_35, new __VLS_35({
            ...{ 'onClick': {} },
            disabled: (__VLS_ctx.loading),
        }));
        const __VLS_37 = __VLS_36({
            ...{ 'onClick': {} },
            disabled: (__VLS_ctx.loading),
        }, ...__VLS_functionalComponentArgsRest(__VLS_36));
        let __VLS_40;
        const __VLS_41 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.invitationsStore.invitations.length))
                        return;
                    __VLS_ctx.accept(invitation.id, invitation.organization_id);
                    // @ts-ignore
                    [loading, accept,];
                } });
        const { default: __VLS_42 } = __VLS_38.slots;
        {
            const { icon: __VLS_43 } = __VLS_38.slots;
            let __VLS_44;
            /** @ts-ignore @type { | typeof __VLS_components.Check} */
            Check;
            // @ts-ignore
            const __VLS_45 = __VLS_asFunctionalComponent1(__VLS_44, new __VLS_44({
                size: (12),
            }));
            const __VLS_46 = __VLS_45({
                size: (12),
            }, ...__VLS_functionalComponentArgsRest(__VLS_45));
            // @ts-ignore
            [];
        }
        // @ts-ignore
        [];
        var __VLS_38;
        var __VLS_39;
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
var __VLS_17;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
