/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref } from 'vue';
import { Button, Dialog, InputText, Select, useToast } from 'primevue';
import { Plus } from 'lucide-vue-next';
import { zodResolver } from '@primevue/forms/resolvers/zod';
import { Form } from '@primevue/forms';
import { z } from 'zod';
import { OrganizationRoleEnum } from './organization.interfaces';
import { useInvitationsStore } from '@/stores/invitations';
import { useOrganizationStore } from '@/stores/organization';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
const INITIAL_DATA = { email: '', role: OrganizationRoleEnum.admin };
const dialogPT = {
    root: {
        style: 'padding: 18px;',
    },
    header: {
        style: 'font-size: 20px; font-weight: 600; text-transform: uppercase; padding-bottom: 12px;',
    },
};
const OPTIONS = [
    {
        label: 'Admin',
        value: OrganizationRoleEnum.admin,
    },
    {
        label: 'Member',
        value: OrganizationRoleEnum.member,
    },
];
const invitationsStore = useInvitationsStore();
const organizationStore = useOrganizationStore();
const toast = useToast();
const initialValues = ref({ ...INITIAL_DATA });
const isMemberLimitExceeded = computed(() => {
    if (!organizationStore.organizationDetails)
        return false;
    return (organizationStore.organizationDetails.members_limit <=
        organizationStore.organizationDetails.total_members);
});
const inviteButtonTooltip = computed(() => {
    if (!isMemberLimitExceeded.value)
        return null;
    return `The organization's member limit has been exceeded. Please contact support to upgrade to a higher plan.`;
});
const resolver = zodResolver(z.object({
    email: z.string().email(),
    role: z.string().min(1),
}));
const visible = ref(false);
const loading = ref(false);
async function onFormSubmit({ values, valid }) {
    if (!valid)
        return;
    loading.value = true;
    try {
        const payload = getPayload(values);
        const invite = await invitationsStore.createInvite(payload);
        organizationStore.addInviteToCurrentOrganization(invite);
        visible.value = false;
        toast.add(simpleSuccessToast('An email invitation was sent to the user.'));
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to create invite'));
    }
    finally {
        loading.value = false;
    }
}
function getPayload(values) {
    if (!organizationStore.currentOrganization)
        throw new Error('Current organization not found');
    return {
        email: values.email,
        role: values.role,
        organization_id: organizationStore.currentOrganization.id,
    };
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['form']} */ ;
/** @type {__VLS_StyleScopedClasses['form-select']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    disabled: (__VLS_ctx.isMemberLimitExceeded),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    disabled: (__VLS_ctx.isMemberLimitExceeded),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.visible = true;
            // @ts-ignore
            [isMemberLimitExceeded, visible,];
        } });
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { top: true, }, value: (__VLS_ctx.inviteButtonTooltip) }, null, null);
const { default: __VLS_7 } = __VLS_3.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
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
// @ts-ignore
[vTooltip, inviteButtonTooltip,];
var __VLS_3;
var __VLS_4;
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    visible: (__VLS_ctx.visible),
    modal: true,
    header: "Invite member",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}));
const __VLS_15 = __VLS_14({
    visible: (__VLS_ctx.visible),
    modal: true,
    header: "Invite member",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
const { default: __VLS_18 } = __VLS_16.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "dialog-content" },
});
/** @type {__VLS_StyleScopedClasses['dialog-content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "dialog-text" },
});
/** @type {__VLS_StyleScopedClasses['dialog-text']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "body" },
});
/** @type {__VLS_StyleScopedClasses['body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "body-title" },
});
/** @type {__VLS_StyleScopedClasses['body-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "body-description" },
});
/** @type {__VLS_StyleScopedClasses['body-description']} */ ;
let __VLS_19;
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
    ...{ 'onSubmit': {} },
    id: "createInviteForm",
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    validateOnValueUpdate: (false),
    ...{ class: "form" },
}));
const __VLS_21 = __VLS_20({
    ...{ 'onSubmit': {} },
    id: "createInviteForm",
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    validateOnValueUpdate: (false),
    ...{ class: "form" },
}, ...__VLS_functionalComponentArgsRest(__VLS_20));
let __VLS_24;
const __VLS_25 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onFormSubmit) });
/** @type {__VLS_StyleScopedClasses['form']} */ ;
{
    const { default: __VLS_26 } = __VLS_22.slots;
    const [{ email }] = __VLS_vSlot(__VLS_26);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "form-field" },
    });
    /** @type {__VLS_StyleScopedClasses['form-field']} */ ;
    let __VLS_27;
    /** @ts-ignore @type { | typeof __VLS_components.InputText} */
    InputText;
    // @ts-ignore
    const __VLS_28 = __VLS_asFunctionalComponent1(__VLS_27, new __VLS_27({
        name: "email",
        placeholder: "Email",
        ...{ class: "form-input" },
        invalid: (email?.invalid),
    }));
    const __VLS_29 = __VLS_28({
        name: "email",
        placeholder: "Email",
        ...{ class: "form-input" },
        invalid: (email?.invalid),
    }, ...__VLS_functionalComponentArgsRest(__VLS_28));
    /** @type {__VLS_StyleScopedClasses['form-input']} */ ;
    if (email?.invalid) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "error-message" },
        });
        /** @type {__VLS_StyleScopedClasses['error-message']} */ ;
    }
    let __VLS_32;
    /** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
    Select;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
        options: (__VLS_ctx.OPTIONS),
        optionLabel: "label",
        optionValue: "value",
        name: "role",
        ...{ class: "form-select" },
    }));
    const __VLS_34 = __VLS_33({
        options: (__VLS_ctx.OPTIONS),
        optionLabel: "label",
        optionValue: "value",
        name: "role",
        ...{ class: "form-select" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    /** @type {__VLS_StyleScopedClasses['form-select']} */ ;
    // @ts-ignore
    [visible, dialogPT, initialValues, resolver, onFormSubmit, OPTIONS,];
    __VLS_22.slots['' /* empty slot name completion */];
}
var __VLS_22;
var __VLS_23;
{
    const { footer: __VLS_37 } = __VLS_16.slots;
    let __VLS_38;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_39 = __VLS_asFunctionalComponent1(__VLS_38, new __VLS_38({
        type: "submit",
        disabled: (__VLS_ctx.loading),
        loading: (__VLS_ctx.loading),
        form: "createInviteForm",
    }));
    const __VLS_40 = __VLS_39({
        type: "submit",
        disabled: (__VLS_ctx.loading),
        loading: (__VLS_ctx.loading),
        form: "createInviteForm",
    }, ...__VLS_functionalComponentArgsRest(__VLS_39));
    const { default: __VLS_43 } = __VLS_41.slots;
    // @ts-ignore
    [loading, loading,];
    var __VLS_41;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_16;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
