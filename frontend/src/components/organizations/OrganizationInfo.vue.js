/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, onMounted, ref, watch } from 'vue';
import { zodResolver } from '@primevue/forms/resolvers/zod';
import { z } from 'zod';
import { Form } from '@primevue/forms';
import { PenLine, UserCog } from 'lucide-vue-next';
import { useOrganizationStore } from '@/stores/organization';
import { Avatar, Button, Dialog, useToast, InputText } from 'primevue';
import OrganizationDelete from './OrganizationDelete.vue';
import UiId from '../ui/UiId.vue';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
const organizationStore = useOrganizationStore();
const toast = useToast();
const dialogPT = {
    footer: {
        class: 'organization-edit-footer',
    },
};
const resolver = zodResolver(z.object({
    name: z.string().min(3),
}));
const initialValues = ref({
    name: '',
});
const visible = ref(false);
const logo = ref(null);
const loading = ref(false);
const avatarLabel = computed(() => {
    return organizationStore.currentOrganization?.name.charAt(0).toUpperCase();
});
function onImageChange(event) {
    logo.value = event;
}
async function onFormSubmit({ values, valid }) {
    if (!valid)
        return;
    const payload = {
        logo: 'https://framerusercontent.com/images/Ks0qcMuaRUt9YEMHOZIkAAXLwl0.png',
        name: values.name,
    };
    try {
        loading.value = true;
        if (!organizationStore.currentOrganization)
            throw new Error('Current organization not found');
        await organizationStore.updateOrganization(organizationStore.currentOrganization.id, payload);
        toast.add(simpleSuccessToast('All changes have been saved.'));
        visible.value = false;
    }
    catch (e) {
        toast.add(simpleErrorToast(e.message || 'Could not create organization'));
    }
    finally {
        loading.value = false;
    }
}
function setOrganizationData() {
    initialValues.value.name = organizationStore.currentOrganization?.name || '';
}
watch(() => organizationStore.currentOrganization, () => setOrganizationData());
onMounted(() => {
    setOrganizationData();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['name']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "info" },
});
/** @type {__VLS_StyleScopedClasses['info']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Avatar} */
Avatar;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    size: "large",
    label: (__VLS_ctx.avatarLabel),
    ...{ class: "avatar" },
}));
const __VLS_2 = __VLS_1({
    size: "large",
    label: (__VLS_ctx.avatarLabel),
    ...{ class: "avatar" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['avatar']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "name" },
});
/** @type {__VLS_StyleScopedClasses['name']} */ ;
(__VLS_ctx.organizationStore.currentOrganization?.name);
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onClick': {} },
    severity: "secondary",
    variant: "text",
    ...{ class: "edit-button" },
}));
const __VLS_7 = __VLS_6({
    ...{ 'onClick': {} },
    severity: "secondary",
    variant: "text",
    ...{ class: "edit-button" },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.visible = true;
            // @ts-ignore
            [avatarLabel, organizationStore, visible,];
        } });
/** @type {__VLS_StyleScopedClasses['edit-button']} */ ;
const { default: __VLS_12 } = __VLS_8.slots;
{
    const { icon: __VLS_13 } = __VLS_8.slots;
    let __VLS_14;
    /** @ts-ignore @type { | typeof __VLS_components.PenLine} */
    PenLine;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        size: (14),
    }));
    const __VLS_16 = __VLS_15({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_8;
var __VLS_9;
if (__VLS_ctx.organizationStore.currentOrganization?.id) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "id-row" },
    });
    /** @type {__VLS_StyleScopedClasses['id-row']} */ ;
    const __VLS_19 = UiId || UiId;
    // @ts-ignore
    const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
        id: (__VLS_ctx.organizationStore.currentOrganization.id),
        variant: "button",
    }));
    const __VLS_21 = __VLS_20({
        id: (__VLS_ctx.organizationStore.currentOrganization.id),
        variant: "button",
    }, ...__VLS_functionalComponentArgsRest(__VLS_20));
}
let __VLS_24;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
    visible: (__VLS_ctx.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}));
const __VLS_26 = __VLS_25({
    visible: (__VLS_ctx.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
const { default: __VLS_29 } = __VLS_27.slots;
{
    const { header: __VLS_30 } = __VLS_27.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "popup-title" },
    });
    /** @type {__VLS_StyleScopedClasses['popup-title']} */ ;
    let __VLS_31;
    /** @ts-ignore @type { | typeof __VLS_components.UserCog} */
    UserCog;
    // @ts-ignore
    const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
        size: (20),
        ...{ class: "popup-title-icon" },
    }));
    const __VLS_33 = __VLS_32({
        size: (20),
        ...{ class: "popup-title-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_32));
    /** @type {__VLS_StyleScopedClasses['popup-title-icon']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [organizationStore, organizationStore, visible, dialogPT,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "dialog-content" },
});
/** @type {__VLS_StyleScopedClasses['dialog-content']} */ ;
let __VLS_36;
/** @ts-ignore @type { | typeof __VLS_components.Avatar} */
Avatar;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent1(__VLS_36, new __VLS_36({
    size: "xlarge",
    label: (__VLS_ctx.avatarLabel),
}));
const __VLS_38 = __VLS_37({
    size: "xlarge",
    label: (__VLS_ctx.avatarLabel),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
let __VLS_41;
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_42 = __VLS_asFunctionalComponent1(__VLS_41, new __VLS_41({
    ...{ 'onSubmit': {} },
    id: "editOrganizationForm",
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    ...{ class: "body" },
}));
const __VLS_43 = __VLS_42({
    ...{ 'onSubmit': {} },
    id: "editOrganizationForm",
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    ...{ class: "body" },
}, ...__VLS_functionalComponentArgsRest(__VLS_42));
let __VLS_46;
const __VLS_47 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onFormSubmit) });
/** @type {__VLS_StyleScopedClasses['body']} */ ;
const { default: __VLS_48 } = __VLS_44.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "name",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_49;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_50 = __VLS_asFunctionalComponent1(__VLS_49, new __VLS_49({
    modelValue: (__VLS_ctx.initialValues.name),
    name: "name",
    id: "name",
    ...{ class: "input" },
}));
const __VLS_51 = __VLS_50({
    modelValue: (__VLS_ctx.initialValues.name),
    name: "name",
    id: "name",
    ...{ class: "input" },
}, ...__VLS_functionalComponentArgsRest(__VLS_50));
/** @type {__VLS_StyleScopedClasses['input']} */ ;
// @ts-ignore
[avatarLabel, initialValues, initialValues, resolver, onFormSubmit,];
var __VLS_44;
var __VLS_45;
{
    const { footer: __VLS_54 } = __VLS_27.slots;
    const __VLS_55 = OrganizationDelete || OrganizationDelete;
    // @ts-ignore
    const __VLS_56 = __VLS_asFunctionalComponent1(__VLS_55, new __VLS_55({}));
    const __VLS_57 = __VLS_56({}, ...__VLS_functionalComponentArgsRest(__VLS_56));
    let __VLS_60;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent1(__VLS_60, new __VLS_60({
        type: "submit",
        form: "editOrganizationForm",
    }));
    const __VLS_62 = __VLS_61({
        type: "submit",
        form: "editOrganizationForm",
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    const { default: __VLS_65 } = __VLS_63.slots;
    // @ts-ignore
    [];
    var __VLS_63;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_27;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
