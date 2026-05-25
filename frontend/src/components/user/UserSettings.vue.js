/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, watch } from 'vue';
import { useInputIcon } from '@/hooks/useInputIcon';
import { useUserStore } from '@/stores/user';
import { useConfirm } from 'primevue/useconfirm';
import { useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { userSettingResolver } from '@/utils/forms/resolvers';
import { userProfileUpdateSuccessToast } from '@/lib/primevue/data/toasts';
import { storeToRefs } from 'pinia';
import { deleteAccountConfirmOptions } from '@/lib/primevue/data/confirm';
const userStore = useUserStore();
const { getUserFullName, getUserEmail, isUserLoggedWithSSO } = storeToRefs(userStore);
const confirm = useConfirm();
const router = useRouter();
const toast = useToast();
const emit = defineEmits();
const initialValues = ref({
    username: getUserFullName.value || '',
    email: getUserEmail.value || '',
});
const resolver = ref(userSettingResolver);
const formRef = ref();
const usernameRef = ref();
const emailRef = ref();
const { getCurrentInputIcon, onIconClick } = useInputIcon([usernameRef, emailRef], formRef, initialValues);
const newAvatar = ref(null);
const formResponseError = ref('');
const showSuccess = (detail) => {
    toast.add(userProfileUpdateSuccessToast(detail));
};
const deleteAccountConfirm = () => {
    const accept = async () => {
        await userStore.deleteAccount();
        router.push({ name: 'sign-up' });
    };
    confirm.require(deleteAccountConfirmOptions(accept));
};
const onAvatarChange = (payload) => {
    newAvatar.value = payload;
};
const onFormSubmit = async ({ valid }) => {
    if (!valid)
        return;
    const data = {};
    if (userStore.getUserFullName !== initialValues.value.username)
        data.full_name = initialValues.value.username;
    if (userStore.getUserEmail !== initialValues.value.email)
        data.email = initialValues.value.email;
    if (newAvatar.value)
        data.photo = newAvatar.value;
    if (!Object.keys(data).length) {
        emit('close');
        return;
    }
    try {
        const response = await userStore.updateUser(data);
        showSuccess(response.detail);
        emit('close');
    }
    catch (e) {
        formResponseError.value = e.response.data.detail || 'Form is invalid';
    }
};
watch(initialValues, () => {
    formResponseError.value = '';
}, { deep: true });
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dForm | typeof __VLS_components.DForm | typeof __VLS_components['d-form'] | typeof __VLS_components.dForm | typeof __VLS_components.DForm | typeof __VLS_components['d-form']} */
dForm;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onSubmit': {} },
    ...{ class: "wrapper" },
    ref: "formRef",
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    validateOnValueUpdate: (false),
    validateOnSubmit: (true),
    validateOnBlur: (true),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onSubmit': {} },
    ...{ class: "wrapper" },
    ref: "formRef",
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    validateOnValueUpdate: (false),
    validateOnSubmit: (true),
    validateOnBlur: (true),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onFormSubmit) });
var __VLS_7;
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
{
    const { default: __VLS_9 } = __VLS_3.slots;
    const [$form] = __VLS_vSlot(__VLS_9);
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.dAvatar | typeof __VLS_components.DAvatar | typeof __VLS_components['d-avatar'] | typeof __VLS_components.dAvatar | typeof __VLS_components.DAvatar | typeof __VLS_components['d-avatar']} */
    dAvatar;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        label: (__VLS_ctx.userStore.getUserAvatar ? undefined : __VLS_ctx.getUserFullName?.[0] || __VLS_ctx.getUserEmail?.[0]),
        image: (__VLS_ctx.userStore.getUserAvatar),
        shape: "circle",
        size: "xlarge",
        ...{ class: "image-input" },
    }));
    const __VLS_12 = __VLS_11({
        label: (__VLS_ctx.userStore.getUserAvatar ? undefined : __VLS_ctx.getUserFullName?.[0] || __VLS_ctx.getUserEmail?.[0]),
        image: (__VLS_ctx.userStore.getUserAvatar),
        shape: "circle",
        size: "xlarge",
        ...{ class: "image-input" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    /** @type {__VLS_StyleScopedClasses['image-input']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "inputs" },
    });
    /** @type {__VLS_StyleScopedClasses['inputs']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "input-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['input-wrapper']} */ ;
    let __VLS_15;
    /** @ts-ignore @type { | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label'] | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label']} */
    dFloatLabel;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
        variant: "on",
    }));
    const __VLS_17 = __VLS_16({
        variant: "on",
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    const { default: __VLS_20 } = __VLS_18.slots;
    let __VLS_21;
    /** @ts-ignore @type { | typeof __VLS_components.dIconField | typeof __VLS_components.DIconField | typeof __VLS_components['d-icon-field'] | typeof __VLS_components.dIconField | typeof __VLS_components.DIconField | typeof __VLS_components['d-icon-field']} */
    dIconField;
    // @ts-ignore
    const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({}));
    const __VLS_23 = __VLS_22({}, ...__VLS_functionalComponentArgsRest(__VLS_22));
    const { default: __VLS_26 } = __VLS_24.slots;
    let __VLS_27;
    /** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
    dInputText;
    // @ts-ignore
    const __VLS_28 = __VLS_asFunctionalComponent1(__VLS_27, new __VLS_27({
        ref: "usernameRef",
        id: "username",
        name: "username",
        fluid: true,
        modelValue: (__VLS_ctx.initialValues.username),
    }));
    const __VLS_29 = __VLS_28({
        ref: "usernameRef",
        id: "username",
        name: "username",
        fluid: true,
        modelValue: (__VLS_ctx.initialValues.username),
    }, ...__VLS_functionalComponentArgsRest(__VLS_28));
    var __VLS_32;
    var __VLS_30;
    let __VLS_34;
    /** @ts-ignore @type { | typeof __VLS_components.dInputIcon | typeof __VLS_components.DInputIcon | typeof __VLS_components['d-input-icon'] | typeof __VLS_components.dInputIcon | typeof __VLS_components.DInputIcon | typeof __VLS_components['d-input-icon']} */
    dInputIcon;
    // @ts-ignore
    const __VLS_35 = __VLS_asFunctionalComponent1(__VLS_34, new __VLS_34({}));
    const __VLS_36 = __VLS_35({}, ...__VLS_functionalComponentArgsRest(__VLS_35));
    const { default: __VLS_39 } = __VLS_37.slots;
    const __VLS_40 = (__VLS_ctx.getCurrentInputIcon('username'));
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
        ...{ 'onClick': {} },
        size: (14),
    }));
    const __VLS_42 = __VLS_41({
        ...{ 'onClick': {} },
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    let __VLS_45;
    const __VLS_46 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.onIconClick('username');
                // @ts-ignore
                [initialValues, initialValues, resolver, onFormSubmit, userStore, userStore, getUserFullName, getUserEmail, getCurrentInputIcon, onIconClick,];
            } });
    var __VLS_43;
    var __VLS_44;
    // @ts-ignore
    [];
    var __VLS_37;
    // @ts-ignore
    [];
    var __VLS_24;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
        for: "username",
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    // @ts-ignore
    [];
    var __VLS_18;
    if ($form.username?.invalid) {
        let __VLS_47;
        /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
        dMessage;
        // @ts-ignore
        const __VLS_48 = __VLS_asFunctionalComponent1(__VLS_47, new __VLS_47({
            severity: "error",
            size: "small",
            variant: "simple",
        }));
        const __VLS_49 = __VLS_48({
            severity: "error",
            size: "small",
            variant: "simple",
        }, ...__VLS_functionalComponentArgsRest(__VLS_48));
        const { default: __VLS_52 } = __VLS_50.slots;
        ($form.username.error?.message);
        // @ts-ignore
        [];
        var __VLS_50;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "input-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['input-wrapper']} */ ;
    let __VLS_53;
    /** @ts-ignore @type { | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label'] | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label']} */
    dFloatLabel;
    // @ts-ignore
    const __VLS_54 = __VLS_asFunctionalComponent1(__VLS_53, new __VLS_53({
        variant: "on",
    }));
    const __VLS_55 = __VLS_54({
        variant: "on",
    }, ...__VLS_functionalComponentArgsRest(__VLS_54));
    const { default: __VLS_58 } = __VLS_56.slots;
    let __VLS_59;
    /** @ts-ignore @type { | typeof __VLS_components.dIconField | typeof __VLS_components.DIconField | typeof __VLS_components['d-icon-field'] | typeof __VLS_components.dIconField | typeof __VLS_components.DIconField | typeof __VLS_components['d-icon-field']} */
    dIconField;
    // @ts-ignore
    const __VLS_60 = __VLS_asFunctionalComponent1(__VLS_59, new __VLS_59({}));
    const __VLS_61 = __VLS_60({}, ...__VLS_functionalComponentArgsRest(__VLS_60));
    const { default: __VLS_64 } = __VLS_62.slots;
    let __VLS_65;
    /** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
    dInputText;
    // @ts-ignore
    const __VLS_66 = __VLS_asFunctionalComponent1(__VLS_65, new __VLS_65({
        ref: "emailRef",
        id: "email",
        name: "email",
        fluid: true,
        disabled: (__VLS_ctx.isUserLoggedWithSSO),
        modelValue: (__VLS_ctx.initialValues.email),
    }));
    const __VLS_67 = __VLS_66({
        ref: "emailRef",
        id: "email",
        name: "email",
        fluid: true,
        disabled: (__VLS_ctx.isUserLoggedWithSSO),
        modelValue: (__VLS_ctx.initialValues.email),
    }, ...__VLS_functionalComponentArgsRest(__VLS_66));
    var __VLS_70;
    var __VLS_68;
    if (!__VLS_ctx.isUserLoggedWithSSO) {
        let __VLS_72;
        /** @ts-ignore @type { | typeof __VLS_components.dInputIcon | typeof __VLS_components.DInputIcon | typeof __VLS_components['d-input-icon'] | typeof __VLS_components.dInputIcon | typeof __VLS_components.DInputIcon | typeof __VLS_components['d-input-icon']} */
        dInputIcon;
        // @ts-ignore
        const __VLS_73 = __VLS_asFunctionalComponent1(__VLS_72, new __VLS_72({}));
        const __VLS_74 = __VLS_73({}, ...__VLS_functionalComponentArgsRest(__VLS_73));
        const { default: __VLS_77 } = __VLS_75.slots;
        const __VLS_78 = (__VLS_ctx.getCurrentInputIcon('email'));
        // @ts-ignore
        const __VLS_79 = __VLS_asFunctionalComponent1(__VLS_78, new __VLS_78({
            ...{ 'onClick': {} },
            size: (14),
        }));
        const __VLS_80 = __VLS_79({
            ...{ 'onClick': {} },
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_79));
        let __VLS_83;
        const __VLS_84 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(!__VLS_ctx.isUserLoggedWithSSO))
                        return;
                    __VLS_ctx.onIconClick('email');
                    // @ts-ignore
                    [initialValues, getCurrentInputIcon, onIconClick, isUserLoggedWithSSO, isUserLoggedWithSSO,];
                } });
        var __VLS_81;
        var __VLS_82;
        // @ts-ignore
        [];
        var __VLS_75;
    }
    // @ts-ignore
    [];
    var __VLS_62;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
        for: "email",
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    // @ts-ignore
    [];
    var __VLS_56;
    if ($form.email?.invalid) {
        let __VLS_85;
        /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
        dMessage;
        // @ts-ignore
        const __VLS_86 = __VLS_asFunctionalComponent1(__VLS_85, new __VLS_85({
            severity: "error",
            size: "small",
            variant: "simple",
        }));
        const __VLS_87 = __VLS_86({
            severity: "error",
            size: "small",
            variant: "simple",
        }, ...__VLS_functionalComponentArgsRest(__VLS_86));
        const { default: __VLS_90 } = __VLS_88.slots;
        ($form.email.error?.message);
        // @ts-ignore
        [];
        var __VLS_88;
    }
    if (__VLS_ctx.formResponseError) {
        let __VLS_91;
        /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
        dMessage;
        // @ts-ignore
        const __VLS_92 = __VLS_asFunctionalComponent1(__VLS_91, new __VLS_91({
            severity: "error",
            size: "small",
            variant: "simple",
        }));
        const __VLS_93 = __VLS_92({
            severity: "error",
            size: "small",
            variant: "simple",
        }, ...__VLS_functionalComponentArgsRest(__VLS_92));
        const { default: __VLS_96 } = __VLS_94.slots;
        (__VLS_ctx.formResponseError);
        // @ts-ignore
        [formResponseError, formResponseError,];
        var __VLS_94;
    }
    if (!__VLS_ctx.isUserLoggedWithSSO) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(!__VLS_ctx.isUserLoggedWithSSO))
                        return;
                    __VLS_ctx.$emit('showChangePassword');
                    // @ts-ignore
                    [isUserLoggedWithSSO, $emit,];
                } },
            ...{ class: "link change-password-link" },
        });
        /** @type {__VLS_StyleScopedClasses['link']} */ ;
        /** @type {__VLS_StyleScopedClasses['change-password-link']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "footer" },
    });
    /** @type {__VLS_StyleScopedClasses['footer']} */ ;
    let __VLS_97;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_98 = __VLS_asFunctionalComponent1(__VLS_97, new __VLS_97({
        ...{ 'onClick': {} },
        label: "delete account",
        severity: "warn",
        variant: "outlined",
    }));
    const __VLS_99 = __VLS_98({
        ...{ 'onClick': {} },
        label: "delete account",
        severity: "warn",
        variant: "outlined",
    }, ...__VLS_functionalComponentArgsRest(__VLS_98));
    let __VLS_102;
    const __VLS_103 = ({ click: {} },
        { onClick: (__VLS_ctx.deleteAccountConfirm) });
    var __VLS_100;
    var __VLS_101;
    let __VLS_104;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_105 = __VLS_asFunctionalComponent1(__VLS_104, new __VLS_104({
        label: "save changes",
        type: "submit",
        disabled: (__VLS_ctx.userStore.isUserDisabled),
    }));
    const __VLS_106 = __VLS_105({
        label: "save changes",
        type: "submit",
        disabled: (__VLS_ctx.userStore.isUserDisabled),
    }, ...__VLS_functionalComponentArgsRest(__VLS_105));
    // @ts-ignore
    [userStore, deleteAccountConfirm,];
    __VLS_3.slots['' /* empty slot name completion */];
}
var __VLS_3;
var __VLS_4;
// @ts-ignore
var __VLS_8 = __VLS_7, __VLS_33 = __VLS_32, __VLS_71 = __VLS_70;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
});
export default {};
