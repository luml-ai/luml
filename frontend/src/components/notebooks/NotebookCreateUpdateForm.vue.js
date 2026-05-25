/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { z } from 'zod';
import { zodResolver } from '@primevue/forms/resolvers/zod';
import { Button } from 'primevue';
const props = defineProps();
const emit = defineEmits();
const initialValues = ref(props.initialData ? { ...props.initialData } : { fullname: '' });
const resolver = zodResolver(z.object({
    fullname: z.string().min(3),
}));
function onFormSubmit({ values, valid }) {
    if (!valid)
        return;
    const payload = { fullname: values.fullname };
    emit('submit', payload);
}
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
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    ...{ class: "form" },
    validateOnValueUpdate: (false),
    validateOnSubmit: (true),
    validateOnBlur: (false),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onSubmit': {} },
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    ...{ class: "form" },
    validateOnValueUpdate: (false),
    validateOnSubmit: (true),
    validateOnBlur: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onFormSubmit) });
var __VLS_7;
/** @type {__VLS_StyleScopedClasses['form']} */ ;
{
    const { default: __VLS_8 } = __VLS_3.slots;
    const [$form] = __VLS_vSlot(__VLS_8);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
        for: "fullname",
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    (__VLS_ctx.updateMode ? 'New name' : 'Name');
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
    dInputText;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        id: "fullname",
        name: "fullname",
        fluid: true,
        modelValue: (__VLS_ctx.initialValues.fullname),
        placeholder: "Instance name",
    }));
    const __VLS_11 = __VLS_10({
        id: "fullname",
        name: "fullname",
        fluid: true,
        modelValue: (__VLS_ctx.initialValues.fullname),
        placeholder: "Instance name",
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    if ($form.fullname?.invalid) {
        let __VLS_14;
        /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
        dMessage;
        // @ts-ignore
        const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
            severity: "error",
            size: "small",
            variant: "simple",
        }));
        const __VLS_16 = __VLS_15({
            severity: "error",
            size: "small",
            variant: "simple",
        }, ...__VLS_functionalComponentArgsRest(__VLS_15));
        const { default: __VLS_19 } = __VLS_17.slots;
        ($form.fullname.error?.message);
        // @ts-ignore
        [initialValues, initialValues, resolver, onFormSubmit, updateMode,];
        var __VLS_17;
    }
    let __VLS_20;
    /** @ts-ignore @type { | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
        type: "submit",
        loading: (__VLS_ctx.loading),
        label: (__VLS_ctx.updateMode ? 'Confirm' : 'Create'),
        rounded: true,
    }));
    const __VLS_22 = __VLS_21({
        type: "submit",
        loading: (__VLS_ctx.loading),
        label: (__VLS_ctx.updateMode ? 'Confirm' : 'Create'),
        rounded: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    // @ts-ignore
    [updateMode, loading,];
    __VLS_3.slots['' /* empty slot name completion */];
}
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
