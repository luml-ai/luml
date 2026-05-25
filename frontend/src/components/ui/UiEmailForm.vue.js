/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { useToast } from 'primevue';
import { simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { forgotPasswordInitialValues } from '@/utils/forms/initialValues';
import { forgotPasswordResolver } from '@/utils/forms/resolvers';
import { useRoute } from 'vue-router';
import { api } from '@/lib/api';
const toast = useToast();
const route = useRoute();
const initialValues = ref({ ...forgotPasswordInitialValues });
const resolver = ref(forgotPasswordResolver);
const loading = ref(false);
const onFormSubmit = async ({ valid, values }) => {
    if (!valid)
        return;
    loading.value = true;
    try {
        const currentPage = route.name;
        await api.sendEmail({ email: values.email, description: currentPage });
        initialValues.value = { ...forgotPasswordInitialValues };
        toast.add(simpleSuccessToast(`We’ll notify you as soon as ${currentPage?.toString()} is ready for early access.`, 'You’re on the list!'));
    }
    catch {
        toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to send email' });
    }
    finally {
        loading.value = false;
    }
};
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['form']} */ ;
/** @type {__VLS_StyleScopedClasses['input-wrapper']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dForm | typeof __VLS_components.DForm | typeof __VLS_components['d-form'] | typeof __VLS_components.dForm | typeof __VLS_components.DForm | typeof __VLS_components['d-form']} */
dForm;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onSubmit': {} },
    ...{ class: "form" },
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    validateOnValueUpdate: (false),
    validateOnSubmit: (true),
    validateOnBlur: (true),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onSubmit': {} },
    ...{ class: "form" },
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
/** @type {__VLS_StyleScopedClasses['form']} */ ;
{
    const { default: __VLS_8 } = __VLS_3.slots;
    const [$form] = __VLS_vSlot(__VLS_8);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "input-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['input-wrapper']} */ ;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label'] | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label']} */
    dFloatLabel;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        variant: "on",
    }));
    const __VLS_11 = __VLS_10({
        variant: "on",
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    const { default: __VLS_14 } = __VLS_12.slots;
    let __VLS_15;
    /** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
    dInputText;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
        id: "email",
        name: "email",
        type: "email",
        autocomplete: "off",
        fluid: true,
        modelValue: (__VLS_ctx.initialValues.email),
        ...{ class: "input" },
        variant: "filled",
    }));
    const __VLS_17 = __VLS_16({
        id: "email",
        name: "email",
        type: "email",
        autocomplete: "off",
        fluid: true,
        modelValue: (__VLS_ctx.initialValues.email),
        ...{ class: "input" },
        variant: "filled",
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    /** @type {__VLS_StyleScopedClasses['input']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: "email",
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    // @ts-ignore
    [initialValues, initialValues, resolver, onFormSubmit,];
    var __VLS_12;
    if ($form.email?.invalid) {
        let __VLS_20;
        /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
        dMessage;
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
            severity: "error",
            size: "small",
            variant: "simple",
            ...{ class: "message" },
        }));
        const __VLS_22 = __VLS_21({
            severity: "error",
            size: "small",
            variant: "simple",
            ...{ class: "message" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_21));
        /** @type {__VLS_StyleScopedClasses['message']} */ ;
        const { default: __VLS_25 } = __VLS_23.slots;
        ($form.email.error?.message);
        // @ts-ignore
        [];
        var __VLS_23;
    }
    let __VLS_26;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
        type: "submit",
        ...{ class: "button" },
        loading: (__VLS_ctx.loading),
    }));
    const __VLS_28 = __VLS_27({
        type: "submit",
        ...{ class: "button" },
        loading: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_27));
    /** @type {__VLS_StyleScopedClasses['button']} */ ;
    const { default: __VLS_31 } = __VLS_29.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    let __VLS_32;
    /** @ts-ignore @type { | typeof __VLS_components.arrowRight | typeof __VLS_components.ArrowRight | typeof __VLS_components['arrow-right']} */
    arrowRight;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
        size: (14),
    }));
    const __VLS_34 = __VLS_33({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    // @ts-ignore
    [loading,];
    var __VLS_29;
    // @ts-ignore
    [];
    __VLS_3.slots['' /* empty slot name completion */];
}
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
