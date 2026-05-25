/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, watch } from 'vue';
import { Button, Dialog, Avatar, Select, useConfirm, useToast } from 'primevue';
import { Form } from '@primevue/forms';
import { useOrganizationStore } from '@/stores/organization';
import { Bolt, UserCog } from 'lucide-vue-next';
import { OrganizationRoleEnum } from './organization.interfaces';
import { zodResolver } from '@primevue/forms/resolvers/zod';
import { z } from 'zod';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { removeOrganizationUserConfirmOptions } from '@/lib/primevue/data/confirm';
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
const dialogPT = {
    footer: {
        class: 'organization-edit-footer',
    },
};
const props = defineProps();
const organizationStore = useOrganizationStore();
const confirm = useConfirm();
const toast = useToast();
const visible = ref(false);
const loading = ref(false);
const initialValues = ref({
    role: props.member.role,
});
const resolver = zodResolver(z.object({
    role: z.string().min(1),
}));
async function onFormSubmit({ values, valid }) {
    if (!valid)
        return;
    try {
        visible.value = false;
        loading.value = true;
        await organizationStore.updateMember(props.member.organization_id, props.member.id, {
            role: values.role,
        });
        toast.add(simpleSuccessToast('User role has been updated.'));
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to update user'));
    }
    finally {
        loading.value = false;
    }
}
function onDelete() {
    confirm.require(removeOrganizationUserConfirmOptions(deleteUser));
}
async function deleteUser() {
    try {
        visible.value = false;
        loading.value = true;
        await organizationStore.deleteMember(props.member.organization_id, props.member.id);
        toast.add(simpleSuccessToast('The user has been successfully removed.'));
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to delete member'));
    }
    finally {
        loading.value = false;
    }
}
watch(() => props.member.role, (role) => {
    initialValues.value.role = role;
});
const __VLS_ctx = {
    ...{},
    ...{},
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
    variant: "text",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    severity: "secondary",
    variant: "text",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.visible = true;
            // @ts-ignore
            [visible,];
        } });
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { icon: __VLS_8 } = __VLS_3.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.Bolt} */
    Bolt;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        size: (14),
    }));
    const __VLS_11 = __VLS_10({
        size: (14),
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
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}));
const __VLS_16 = __VLS_15({
    visible: (__VLS_ctx.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
const { default: __VLS_19 } = __VLS_17.slots;
{
    const { header: __VLS_20 } = __VLS_17.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "popup-title" },
    });
    /** @type {__VLS_StyleScopedClasses['popup-title']} */ ;
    let __VLS_21;
    /** @ts-ignore @type { | typeof __VLS_components.UserCog} */
    UserCog;
    // @ts-ignore
    const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
        size: (20),
        ...{ class: "popup-title-icon" },
    }));
    const __VLS_23 = __VLS_22({
        size: (20),
        ...{ class: "popup-title-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_22));
    /** @type {__VLS_StyleScopedClasses['popup-title-icon']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [visible, dialogPT,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "dialog-content" },
});
/** @type {__VLS_StyleScopedClasses['dialog-content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "user-info" },
});
/** @type {__VLS_StyleScopedClasses['user-info']} */ ;
let __VLS_26;
/** @ts-ignore @type { | typeof __VLS_components.Avatar} */
Avatar;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
    label: (__VLS_ctx.member.user.photo ? undefined : __VLS_ctx.member.user.full_name[0]),
    shape: "circle",
    size: "xlarge",
    image: (__VLS_ctx.member.user.photo),
}));
const __VLS_28 = __VLS_27({
    label: (__VLS_ctx.member.user.photo ? undefined : __VLS_ctx.member.user.full_name[0]),
    shape: "circle",
    size: "xlarge",
    image: (__VLS_ctx.member.user.photo),
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "user-name" },
});
/** @type {__VLS_StyleScopedClasses['user-name']} */ ;
(__VLS_ctx.member.user.full_name);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "user-email" },
});
/** @type {__VLS_StyleScopedClasses['user-email']} */ ;
(__VLS_ctx.member.user.email);
let __VLS_31;
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
    ...{ 'onSubmit': {} },
    id: "editOrganizationForm",
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    ...{ class: "body" },
}));
const __VLS_33 = __VLS_32({
    ...{ 'onSubmit': {} },
    id: "editOrganizationForm",
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    ...{ class: "body" },
}, ...__VLS_functionalComponentArgsRest(__VLS_32));
let __VLS_36;
const __VLS_37 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onFormSubmit) });
/** @type {__VLS_StyleScopedClasses['body']} */ ;
const { default: __VLS_38 } = __VLS_34.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "role",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_39;
/** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_40 = __VLS_asFunctionalComponent1(__VLS_39, new __VLS_39({
    options: (__VLS_ctx.OPTIONS),
    optionLabel: "label",
    optionValue: "value",
    name: "role",
    id: "role",
    fluid: true,
}));
const __VLS_41 = __VLS_40({
    options: (__VLS_ctx.OPTIONS),
    optionLabel: "label",
    optionValue: "value",
    name: "role",
    id: "role",
    fluid: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_40));
// @ts-ignore
[member, member, member, member, member, initialValues, resolver, onFormSubmit, OPTIONS,];
var __VLS_34;
var __VLS_35;
{
    const { footer: __VLS_44 } = __VLS_17.slots;
    let __VLS_45;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({
        ...{ 'onClick': {} },
        severity: "warn",
        variant: "outlined",
        disabled: (__VLS_ctx.loading),
    }));
    const __VLS_47 = __VLS_46({
        ...{ 'onClick': {} },
        severity: "warn",
        variant: "outlined",
        disabled: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_46));
    let __VLS_50;
    const __VLS_51 = ({ click: {} },
        { onClick: (__VLS_ctx.onDelete) });
    const { default: __VLS_52 } = __VLS_48.slots;
    // @ts-ignore
    [loading, onDelete,];
    var __VLS_48;
    var __VLS_49;
    let __VLS_53;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_54 = __VLS_asFunctionalComponent1(__VLS_53, new __VLS_53({
        type: "submit",
        disabled: (__VLS_ctx.loading),
        form: "editOrganizationForm",
    }));
    const __VLS_55 = __VLS_54({
        type: "submit",
        disabled: (__VLS_ctx.loading),
        form: "editOrganizationForm",
    }, ...__VLS_functionalComponentArgsRest(__VLS_54));
    const { default: __VLS_58 } = __VLS_56.slots;
    // @ts-ignore
    [loading,];
    var __VLS_56;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_17;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
