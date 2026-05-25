/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { BucketTypeEnum } from '@/lib/api/bucket-secrets/interfaces';
import { ref, watch, computed } from 'vue';
import { z } from 'zod';
import { Form } from '@primevue/forms';
import { Button, InputText } from 'primevue';
import { zodResolver } from '@primevue/forms/resolvers/zod';
const props = withDefaults(defineProps(), {
    showSubmitButton: true,
});
const emits = defineEmits();
const initialValues = ref({
    type: BucketTypeEnum.azure,
    endpoint: props.initialData?.endpoint || '',
    bucket_name: props.initialData?.bucket_name || '',
});
watch(() => props.initialData, (data) => {
    if (data) {
        initialValues.value.endpoint = data.endpoint || '';
        initialValues.value.bucket_name = data.bucket_name || '';
    }
});
const createBucketResolver = zodResolver(z.object({
    endpoint: z.string().min(1),
    bucket_name: z.string().min(1),
}));
const updateBucketResolver = zodResolver(z.object({
    endpoint: z.string().optional(),
    bucket_name: z.string().optional(),
}));
const resolver = computed(() => (props.update ? updateBucketResolver : createBucketResolver));
function onSubmit({ valid }) {
    if (!valid)
        return;
    if (props.update) {
        const formData = {
            type: BucketTypeEnum.azure,
            endpoint: initialValues.value.endpoint || props.initialData?.endpoint || '',
            bucket_name: initialValues.value.bucket_name || props.initialData?.bucket_name || '',
        };
        emits('submit', formData);
    }
    else {
        emits('submit', { ...initialValues.value });
    }
}
const __VLS_defaults = {
    showSubmitButton: true,
};
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
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onSubmit': {} },
    id: "bucketForm",
    initialValues: (__VLS_ctx.initialValues),
    resolver: (__VLS_ctx.resolver),
    ...{ class: "form" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onSubmit': {} },
    id: "bucketForm",
    initialValues: (__VLS_ctx.initialValues),
    resolver: (__VLS_ctx.resolver),
    ...{ class: "form" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onSubmit) });
var __VLS_7;
/** @type {__VLS_StyleScopedClasses['form']} */ ;
{
    const { default: __VLS_8 } = __VLS_3.slots;
    const [$form] = __VLS_vSlot(__VLS_8);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "inputs" },
    });
    /** @type {__VLS_StyleScopedClasses['inputs']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: "bucket_name",
        ...{ class: "label required" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    /** @type {__VLS_StyleScopedClasses['required']} */ ;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.InputText} */
    InputText;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        modelValue: (__VLS_ctx.initialValues.bucket_name),
        id: "bucket_name",
        name: "bucket_name",
        type: "text",
        placeholder: "Enter container name",
        fluid: true,
    }));
    const __VLS_11 = __VLS_10({
        modelValue: (__VLS_ctx.initialValues.bucket_name),
        id: "bucket_name",
        name: "bucket_name",
        type: "text",
        placeholder: "Enter container name",
        fluid: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    if ($form.bucket_name?.invalid) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "message" },
        });
        /** @type {__VLS_StyleScopedClasses['message']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: "endpoint",
        ...{ class: "label required" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    /** @type {__VLS_StyleScopedClasses['required']} */ ;
    let __VLS_14;
    /** @ts-ignore @type { | typeof __VLS_components.InputText} */
    InputText;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        modelValue: (__VLS_ctx.initialValues.endpoint),
        id: "endpoint",
        name: "endpoint",
        type: "text",
        placeholder: "Enter connection string",
        fluid: true,
    }));
    const __VLS_16 = __VLS_15({
        modelValue: (__VLS_ctx.initialValues.endpoint),
        id: "endpoint",
        name: "endpoint",
        type: "text",
        placeholder: "Enter connection string",
        fluid: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    if ($form.endpoint?.invalid) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "message" },
        });
        /** @type {__VLS_StyleScopedClasses['message']} */ ;
    }
    if (__VLS_ctx.showSubmitButton) {
        let __VLS_19;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
            type: "submit",
            fluid: true,
            rounded: true,
            loading: (__VLS_ctx.loading),
        }));
        const __VLS_21 = __VLS_20({
            type: "submit",
            fluid: true,
            rounded: true,
            loading: (__VLS_ctx.loading),
        }, ...__VLS_functionalComponentArgsRest(__VLS_20));
        const { default: __VLS_24 } = __VLS_22.slots;
        // @ts-ignore
        [initialValues, initialValues, initialValues, resolver, onSubmit, showSubmitButton, loading,];
        var __VLS_22;
    }
    // @ts-ignore
    [];
    __VLS_3.slots['' /* empty slot name completion */];
}
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};
