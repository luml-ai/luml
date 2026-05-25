/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, watch } from 'vue';
import { useUserStore } from '@/stores/user';
import { userChangePasswordResolver } from '@/utils/forms/resolvers';
import { userChangePasswordInitialValues } from '@/utils/forms/initialValues';
const emit = defineEmits(['success']);
const userStore = useUserStore();
const initialValues = ref(userChangePasswordInitialValues);
const resolver = ref(userChangePasswordResolver);
const formResponseError = ref('');
const onFormSubmit = async ({ valid, values }) => {
    if (!valid)
        return;
    const data = {
        current_password: values.current_password,
        new_password: values.new_password,
    };
    try {
        await userStore.changePassword(data);
        emit('success');
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
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    validateOnValueUpdate: (false),
    validateOnSubmit: (true),
    validateOnBlur: (true),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onSubmit': {} },
    ...{ class: "wrapper" },
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
    const { default: __VLS_8 } = __VLS_3.slots;
    const [$form] = __VLS_vSlot(__VLS_8);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "inputs" },
    });
    /** @type {__VLS_StyleScopedClasses['inputs']} */ ;
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
    /** @ts-ignore @type { | typeof __VLS_components.dPassword | typeof __VLS_components.DPassword | typeof __VLS_components['d-password']} */
    dPassword;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
        id: "oldPassword",
        name: "current_password",
        feedback: (false),
        fluid: true,
        toggleMask: true,
        modelValue: (__VLS_ctx.initialValues.current_password),
    }));
    const __VLS_17 = __VLS_16({
        id: "oldPassword",
        name: "current_password",
        feedback: (false),
        fluid: true,
        toggleMask: true,
        modelValue: (__VLS_ctx.initialValues.current_password),
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
        for: "oldPassword",
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    // @ts-ignore
    [initialValues, initialValues, resolver, onFormSubmit,];
    var __VLS_12;
    if ($form.current_password?.invalid) {
        let __VLS_20;
        /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
        dMessage;
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
            severity: "error",
            size: "small",
            variant: "simple",
        }));
        const __VLS_22 = __VLS_21({
            severity: "error",
            size: "small",
            variant: "simple",
        }, ...__VLS_functionalComponentArgsRest(__VLS_21));
        const { default: __VLS_25 } = __VLS_23.slots;
        ($form.current_password.error?.message);
        // @ts-ignore
        [];
        var __VLS_23;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "input-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['input-wrapper']} */ ;
    let __VLS_26;
    /** @ts-ignore @type { | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label'] | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label']} */
    dFloatLabel;
    // @ts-ignore
    const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
        variant: "on",
    }));
    const __VLS_28 = __VLS_27({
        variant: "on",
    }, ...__VLS_functionalComponentArgsRest(__VLS_27));
    const { default: __VLS_31 } = __VLS_29.slots;
    let __VLS_32;
    /** @ts-ignore @type { | typeof __VLS_components.dPassword | typeof __VLS_components.DPassword | typeof __VLS_components['d-password']} */
    dPassword;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
        id: "newPassword",
        name: "new_password",
        feedback: (false),
        fluid: true,
        toggleMask: true,
        modelValue: (__VLS_ctx.initialValues.new_password),
    }));
    const __VLS_34 = __VLS_33({
        id: "newPassword",
        name: "new_password",
        feedback: (false),
        fluid: true,
        toggleMask: true,
        modelValue: (__VLS_ctx.initialValues.new_password),
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
        for: "newPassword",
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    // @ts-ignore
    [initialValues,];
    var __VLS_29;
    if ($form.new_password?.invalid) {
        let __VLS_37;
        /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
        dMessage;
        // @ts-ignore
        const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
            severity: "error",
            size: "small",
            variant: "simple",
        }));
        const __VLS_39 = __VLS_38({
            severity: "error",
            size: "small",
            variant: "simple",
        }, ...__VLS_functionalComponentArgsRest(__VLS_38));
        const { default: __VLS_42 } = __VLS_40.slots;
        ($form.new_password.error?.message);
        // @ts-ignore
        [];
        var __VLS_40;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "input-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['input-wrapper']} */ ;
    let __VLS_43;
    /** @ts-ignore @type { | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label'] | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label']} */
    dFloatLabel;
    // @ts-ignore
    const __VLS_44 = __VLS_asFunctionalComponent1(__VLS_43, new __VLS_43({
        variant: "on",
    }));
    const __VLS_45 = __VLS_44({
        variant: "on",
    }, ...__VLS_functionalComponentArgsRest(__VLS_44));
    const { default: __VLS_48 } = __VLS_46.slots;
    let __VLS_49;
    /** @ts-ignore @type { | typeof __VLS_components.dPassword | typeof __VLS_components.DPassword | typeof __VLS_components['d-password']} */
    dPassword;
    // @ts-ignore
    const __VLS_50 = __VLS_asFunctionalComponent1(__VLS_49, new __VLS_49({
        id: "confirmPassword",
        name: "confirmPassword",
        feedback: (false),
        fluid: true,
        toggleMask: true,
        modelValue: (__VLS_ctx.initialValues.confirmPassword),
    }));
    const __VLS_51 = __VLS_50({
        id: "confirmPassword",
        name: "confirmPassword",
        feedback: (false),
        fluid: true,
        toggleMask: true,
        modelValue: (__VLS_ctx.initialValues.confirmPassword),
    }, ...__VLS_functionalComponentArgsRest(__VLS_50));
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
        for: "confirmPassword",
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    // @ts-ignore
    [initialValues,];
    var __VLS_46;
    if ($form.confirmPassword?.invalid) {
        let __VLS_54;
        /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
        dMessage;
        // @ts-ignore
        const __VLS_55 = __VLS_asFunctionalComponent1(__VLS_54, new __VLS_54({
            severity: "error",
            size: "small",
            variant: "simple",
        }));
        const __VLS_56 = __VLS_55({
            severity: "error",
            size: "small",
            variant: "simple",
        }, ...__VLS_functionalComponentArgsRest(__VLS_55));
        const { default: __VLS_59 } = __VLS_57.slots;
        ($form.confirmPassword.error?.message);
        // @ts-ignore
        [];
        var __VLS_57;
    }
    if (__VLS_ctx.formResponseError) {
        let __VLS_60;
        /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
        dMessage;
        // @ts-ignore
        const __VLS_61 = __VLS_asFunctionalComponent1(__VLS_60, new __VLS_60({
            severity: "error",
            size: "small",
            variant: "simple",
        }));
        const __VLS_62 = __VLS_61({
            severity: "error",
            size: "small",
            variant: "simple",
        }, ...__VLS_functionalComponentArgsRest(__VLS_61));
        const { default: __VLS_65 } = __VLS_63.slots;
        (__VLS_ctx.formResponseError);
        // @ts-ignore
        [formResponseError, formResponseError,];
        var __VLS_63;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "footer" },
    });
    /** @type {__VLS_StyleScopedClasses['footer']} */ ;
    let __VLS_66;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_67 = __VLS_asFunctionalComponent1(__VLS_66, new __VLS_66({
        label: "save changes",
        type: "submit",
    }));
    const __VLS_68 = __VLS_67({
        label: "save changes",
        type: "submit",
    }, ...__VLS_functionalComponentArgsRest(__VLS_67));
    // @ts-ignore
    [];
    __VLS_3.slots['' /* empty slot name completion */];
}
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    emits: {},
});
export default {};
