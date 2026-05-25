/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import AuthorizationWrapper from '@/components/authorization/AuthorizationWrapper.vue';
import MainImage from '@/assets/img/form-bg.webp';
import { useToast } from 'primevue/usetoast';
import { useAuthStore } from '@/stores/auth';
import { forgotPasswordInitialValues } from '@/utils/forms/initialValues';
import { forgotPasswordResolver } from '@/utils/forms/resolvers';
import { emailSentVerifyToast, unknownErrorToast } from '@/lib/primevue/data/toasts';
const toast = useToast();
const authStore = useAuthStore();
const initialValues = ref(forgotPasswordInitialValues);
const resolver = ref(forgotPasswordResolver);
const showSuccess = () => {
    toast.add(emailSentVerifyToast);
};
const onFormSubmit = async ({ valid }) => {
    if (!valid)
        return;
    try {
        await authStore.forgotPassword(initialValues.value.email);
        showSuccess();
    }
    catch (e) {
        toast.add(unknownErrorToast);
    }
};
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
    title: "Forgot password?",
    subTitle: "Enter your email to receive a new password",
    image: (__VLS_ctx.MainImage),
    hideSso: (true),
}));
const __VLS_2 = __VLS_1({
    title: "Forgot password?",
    subTitle: "Enter your email to receive a new password",
    image: (__VLS_ctx.MainImage),
    hideSso: (true),
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
        initialValues: __VLS_ctx.initialValues,
        resolver: __VLS_ctx.resolver,
        validateOnValueUpdate: (false),
        validateOnSubmit: (true),
        validateOnBlur: (true),
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onSubmit': {} },
        ...{ class: "form" },
        initialValues: __VLS_ctx.initialValues,
        resolver: __VLS_ctx.resolver,
        validateOnValueUpdate: (false),
        validateOnSubmit: (true),
        validateOnBlur: (true),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_13;
    const __VLS_14 = ({ submit: {} },
        { onSubmit: (__VLS_ctx.onFormSubmit) });
    /** @type {__VLS_StyleScopedClasses['form']} */ ;
    {
        const { default: __VLS_15 } = __VLS_11.slots;
        const [$form] = __VLS_vSlot(__VLS_15);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "input-wrapper" },
        });
        /** @type {__VLS_StyleScopedClasses['input-wrapper']} */ ;
        let __VLS_16;
        /** @ts-ignore @type { | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label'] | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label']} */
        dFloatLabel;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({
            variant: "on",
        }));
        const __VLS_18 = __VLS_17({
            variant: "on",
        }, ...__VLS_functionalComponentArgsRest(__VLS_17));
        const { default: __VLS_21 } = __VLS_19.slots;
        let __VLS_22;
        /** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
        dInputText;
        // @ts-ignore
        const __VLS_23 = __VLS_asFunctionalComponent1(__VLS_22, new __VLS_22({
            id: "email",
            name: "email",
            type: "email",
            autocomplete: "off",
            fluid: true,
            modelValue: (__VLS_ctx.initialValues.email),
        }));
        const __VLS_24 = __VLS_23({
            id: "email",
            name: "email",
            type: "email",
            autocomplete: "off",
            fluid: true,
            modelValue: (__VLS_ctx.initialValues.email),
        }, ...__VLS_functionalComponentArgsRest(__VLS_23));
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            for: "email",
            ...{ class: "label" },
        });
        /** @type {__VLS_StyleScopedClasses['label']} */ ;
        // @ts-ignore
        [MainImage, initialValues, initialValues, resolver, onFormSubmit,];
        var __VLS_19;
        if ($form.email?.invalid) {
            let __VLS_27;
            /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
            dMessage;
            // @ts-ignore
            const __VLS_28 = __VLS_asFunctionalComponent1(__VLS_27, new __VLS_27({
                severity: "error",
                size: "small",
                variant: "simple",
            }));
            const __VLS_29 = __VLS_28({
                severity: "error",
                size: "small",
                variant: "simple",
            }, ...__VLS_functionalComponentArgsRest(__VLS_28));
            const { default: __VLS_32 } = __VLS_30.slots;
            ($form.email.error?.message);
            // @ts-ignore
            [];
            var __VLS_30;
        }
        let __VLS_33;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_34 = __VLS_asFunctionalComponent1(__VLS_33, new __VLS_33({
            type: "submit",
            label: "Send email",
            rounded: true,
        }));
        const __VLS_35 = __VLS_34({
            type: "submit",
            label: "Send email",
            rounded: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_34));
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
    const { footer: __VLS_38 } = __VLS_3.slots;
    let __VLS_39;
    /** @ts-ignore @type { | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link'] | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link']} */
    routerLink;
    // @ts-ignore
    const __VLS_40 = __VLS_asFunctionalComponent1(__VLS_39, new __VLS_39({
        to: ({ name: 'sign-in' }),
        ...{ class: "link" },
    }));
    const __VLS_41 = __VLS_40({
        to: ({ name: 'sign-in' }),
        ...{ class: "link" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_40));
    /** @type {__VLS_StyleScopedClasses['link']} */ ;
    const { default: __VLS_44 } = __VLS_42.slots;
    // @ts-ignore
    [];
    var __VLS_42;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
