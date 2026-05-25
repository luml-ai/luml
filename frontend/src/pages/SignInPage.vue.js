/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, watch } from 'vue';
import AuthorizationWrapper from '@/components/authorization/AuthorizationWrapper.vue';
import MainImage from '@/assets/img/form-bg.webp';
import { signInInitialValues } from '@/utils/forms/initialValues';
import { signInResolver } from '@/utils/forms/resolvers';
import { useAuthStore } from '@/stores/auth';
import { useRouter } from 'vue-router';
import { useInputIcon } from '@/hooks/useInputIcon';
const authStore = useAuthStore();
const router = useRouter();
const initialValues = ref(signInInitialValues);
const resolver = ref(signInResolver);
const formRef = ref();
const emailRef = ref(null);
const formResponseError = ref('');
const { getCurrentInputIcon, onIconClick } = useInputIcon([emailRef], formRef, initialValues, false);
const onFormSubmit = async ({ valid, values }) => {
    if (!valid)
        return;
    const data = {
        email: values.email,
        password: values.password,
    };
    try {
        await authStore.signIn(data);
        const redirect = router.currentRoute.value.query.redirect;
        router.push(redirect || { name: 'home' });
    }
    catch (e) {
        const errorDetails = e.response?.data.detail;
        if (typeof errorDetails === 'string')
            formResponseError.value = e.response.data.detail;
        else if (typeof errorDetails === 'object') {
            formResponseError.value = errorDetails[0]?.msg;
        }
        else
            formResponseError.value = 'Form is invalid';
    }
};
watch(initialValues, () => {
    formResponseError.value = '';
}, { deep: true });
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
const __VLS_0 = AuthorizationWrapper || AuthorizationWrapper;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    title: "Sign in",
    subTitle: "Welcome to LUML",
    image: (__VLS_ctx.MainImage),
}));
const __VLS_2 = __VLS_1({
    title: "Sign in",
    subTitle: "Welcome to LUML",
    image: (__VLS_ctx.MainImage),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
{
    const { form: __VLS_7 } = __VLS_3.slots;
    let __VLS_8;
    /** @ts-ignore @type { | typeof __VLS_components.dForm | typeof __VLS_components.DForm | typeof __VLS_components['d-form'] | typeof __VLS_components.dForm | typeof __VLS_components.DForm | typeof __VLS_components['d-form']} */
    dForm;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        ...{ 'onSubmit': {} },
        ...{ class: "form" },
        ref: "formRef",
        initialValues: __VLS_ctx.initialValues,
        resolver: __VLS_ctx.resolver,
        validateOnValueUpdate: (false),
        validateOnSubmit: (true),
        validateOnBlur: (true),
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onSubmit': {} },
        ...{ class: "form" },
        ref: "formRef",
        initialValues: __VLS_ctx.initialValues,
        resolver: __VLS_ctx.resolver,
        validateOnValueUpdate: (false),
        validateOnSubmit: (true),
        validateOnBlur: (true),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_13;
    const __VLS_14 = ({ submit: {} },
        { onSubmit: (__VLS_ctx.onFormSubmit) });
    var __VLS_15;
    /** @type {__VLS_StyleScopedClasses['form']} */ ;
    {
        const { default: __VLS_17 } = __VLS_11.slots;
        const [$form] = __VLS_vSlot(__VLS_17);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "inputs" },
        });
        /** @type {__VLS_StyleScopedClasses['inputs']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "input-wrapper" },
        });
        /** @type {__VLS_StyleScopedClasses['input-wrapper']} */ ;
        let __VLS_18;
        /** @ts-ignore @type { | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label'] | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label']} */
        dFloatLabel;
        // @ts-ignore
        const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
            variant: "on",
        }));
        const __VLS_20 = __VLS_19({
            variant: "on",
        }, ...__VLS_functionalComponentArgsRest(__VLS_19));
        const { default: __VLS_23 } = __VLS_21.slots;
        let __VLS_24;
        /** @ts-ignore @type { | typeof __VLS_components.dIconField | typeof __VLS_components.DIconField | typeof __VLS_components['d-icon-field'] | typeof __VLS_components.dIconField | typeof __VLS_components.DIconField | typeof __VLS_components['d-icon-field']} */
        dIconField;
        // @ts-ignore
        const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({}));
        const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
        const { default: __VLS_29 } = __VLS_27.slots;
        let __VLS_30;
        /** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
        dInputText;
        // @ts-ignore
        const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
            ref: "emailRef",
            id: "email",
            name: "email",
            fluid: true,
            type: "text",
            autocomplete: "off",
            modelValue: (__VLS_ctx.initialValues.email),
        }));
        const __VLS_32 = __VLS_31({
            ref: "emailRef",
            id: "email",
            name: "email",
            fluid: true,
            type: "text",
            autocomplete: "off",
            modelValue: (__VLS_ctx.initialValues.email),
        }, ...__VLS_functionalComponentArgsRest(__VLS_31));
        var __VLS_35;
        var __VLS_33;
        let __VLS_37;
        /** @ts-ignore @type { | typeof __VLS_components.dInputIcon | typeof __VLS_components.DInputIcon | typeof __VLS_components['d-input-icon'] | typeof __VLS_components.dInputIcon | typeof __VLS_components.DInputIcon | typeof __VLS_components['d-input-icon']} */
        dInputIcon;
        // @ts-ignore
        const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({}));
        const __VLS_39 = __VLS_38({}, ...__VLS_functionalComponentArgsRest(__VLS_38));
        const { default: __VLS_42 } = __VLS_40.slots;
        const __VLS_43 = (__VLS_ctx.getCurrentInputIcon('email'));
        // @ts-ignore
        const __VLS_44 = __VLS_asFunctionalComponent1(__VLS_43, new __VLS_43({
            ...{ 'onClick': {} },
            size: (14),
        }));
        const __VLS_45 = __VLS_44({
            ...{ 'onClick': {} },
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_44));
        let __VLS_48;
        const __VLS_49 = ({ click: {} },
            { onClick: (...[$event]) => {
                    __VLS_ctx.onIconClick('email');
                    // @ts-ignore
                    [MainImage, initialValues, initialValues, resolver, onFormSubmit, getCurrentInputIcon, onIconClick,];
                } });
        var __VLS_46;
        var __VLS_47;
        // @ts-ignore
        [];
        var __VLS_40;
        // @ts-ignore
        [];
        var __VLS_27;
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            for: "email",
            ...{ class: "label" },
        });
        /** @type {__VLS_StyleScopedClasses['label']} */ ;
        // @ts-ignore
        [];
        var __VLS_21;
        if ($form.email?.invalid) {
            let __VLS_50;
            /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
            dMessage;
            // @ts-ignore
            const __VLS_51 = __VLS_asFunctionalComponent1(__VLS_50, new __VLS_50({
                severity: "error",
                size: "small",
                variant: "simple",
            }));
            const __VLS_52 = __VLS_51({
                severity: "error",
                size: "small",
                variant: "simple",
            }, ...__VLS_functionalComponentArgsRest(__VLS_51));
            const { default: __VLS_55 } = __VLS_53.slots;
            ($form.email.error?.message);
            // @ts-ignore
            [];
            var __VLS_53;
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "input-wrapper" },
        });
        /** @type {__VLS_StyleScopedClasses['input-wrapper']} */ ;
        let __VLS_56;
        /** @ts-ignore @type { | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label'] | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label']} */
        dFloatLabel;
        // @ts-ignore
        const __VLS_57 = __VLS_asFunctionalComponent1(__VLS_56, new __VLS_56({
            variant: "on",
        }));
        const __VLS_58 = __VLS_57({
            variant: "on",
        }, ...__VLS_functionalComponentArgsRest(__VLS_57));
        const { default: __VLS_61 } = __VLS_59.slots;
        let __VLS_62;
        /** @ts-ignore @type { | typeof __VLS_components.dPassword | typeof __VLS_components.DPassword | typeof __VLS_components['d-password']} */
        dPassword;
        // @ts-ignore
        const __VLS_63 = __VLS_asFunctionalComponent1(__VLS_62, new __VLS_62({
            id: "password",
            name: "password",
            fluid: true,
            autocomplete: "off",
            toggleMask: true,
            feedback: (false),
            modelValue: (__VLS_ctx.initialValues.password),
        }));
        const __VLS_64 = __VLS_63({
            id: "password",
            name: "password",
            fluid: true,
            autocomplete: "off",
            toggleMask: true,
            feedback: (false),
            modelValue: (__VLS_ctx.initialValues.password),
        }, ...__VLS_functionalComponentArgsRest(__VLS_63));
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            for: "password",
            ...{ class: "label" },
        });
        /** @type {__VLS_StyleScopedClasses['label']} */ ;
        // @ts-ignore
        [initialValues,];
        var __VLS_59;
        if ($form.password?.invalid) {
            let __VLS_67;
            /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
            dMessage;
            // @ts-ignore
            const __VLS_68 = __VLS_asFunctionalComponent1(__VLS_67, new __VLS_67({
                severity: "error",
                size: "small",
                variant: "simple",
            }));
            const __VLS_69 = __VLS_68({
                severity: "error",
                size: "small",
                variant: "simple",
            }, ...__VLS_functionalComponentArgsRest(__VLS_68));
            const { default: __VLS_72 } = __VLS_70.slots;
            ($form.password.error?.message);
            // @ts-ignore
            [];
            var __VLS_70;
        }
        let __VLS_73;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_74 = __VLS_asFunctionalComponent1(__VLS_73, new __VLS_73({
            type: "submit",
            label: "Sign in",
            rounded: true,
        }));
        const __VLS_75 = __VLS_74({
            type: "submit",
            label: "Sign in",
            rounded: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_74));
        if (__VLS_ctx.formResponseError) {
            let __VLS_78;
            /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
            dMessage;
            // @ts-ignore
            const __VLS_79 = __VLS_asFunctionalComponent1(__VLS_78, new __VLS_78({
                severity: "error",
                size: "small",
                variant: "simple",
            }));
            const __VLS_80 = __VLS_79({
                severity: "error",
                size: "small",
                variant: "simple",
            }, ...__VLS_functionalComponentArgsRest(__VLS_79));
            const { default: __VLS_83 } = __VLS_81.slots;
            (__VLS_ctx.formResponseError);
            // @ts-ignore
            [formResponseError, formResponseError,];
            var __VLS_81;
        }
        // @ts-ignore
        [];
        __VLS_11.slots['' /* empty slot name completion */];
    }
    var __VLS_11;
    var __VLS_12;
    // @ts-ignore
    [];
}
{
    const { footer: __VLS_84 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "footer-message" },
    });
    /** @type {__VLS_StyleScopedClasses['footer-message']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    let __VLS_85;
    /** @ts-ignore @type { | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link'] | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link']} */
    routerLink;
    // @ts-ignore
    const __VLS_86 = __VLS_asFunctionalComponent1(__VLS_85, new __VLS_85({
        to: ({ name: 'sign-up' }),
        ...{ class: "link" },
    }));
    const __VLS_87 = __VLS_86({
        to: ({ name: 'sign-up' }),
        ...{ class: "link" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_86));
    /** @type {__VLS_StyleScopedClasses['link']} */ ;
    const { default: __VLS_90 } = __VLS_88.slots;
    // @ts-ignore
    [];
    var __VLS_88;
    let __VLS_91;
    /** @ts-ignore @type { | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link'] | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link']} */
    routerLink;
    // @ts-ignore
    const __VLS_92 = __VLS_asFunctionalComponent1(__VLS_91, new __VLS_91({
        to: ({ name: 'forgot-password' }),
        ...{ class: "link" },
    }));
    const __VLS_93 = __VLS_92({
        to: ({ name: 'forgot-password' }),
        ...{ class: "link" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_92));
    /** @type {__VLS_StyleScopedClasses['link']} */ ;
    const { default: __VLS_96 } = __VLS_94.slots;
    // @ts-ignore
    [];
    var __VLS_94;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
var __VLS_16 = __VLS_15, __VLS_36 = __VLS_35;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
