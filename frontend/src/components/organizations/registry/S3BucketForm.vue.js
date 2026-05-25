/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { BucketTypeEnum } from '@/lib/api/bucket-secrets/interfaces';
import { ref, watch, computed } from 'vue';
import { z } from 'zod';
import { Form } from '@primevue/forms';
import { Button, InputText, ToggleSwitch } from 'primevue';
import { zodResolver } from '@primevue/forms/resolvers/zod';
const props = withDefaults(defineProps(), {
    showSubmitButton: true,
});
const emits = defineEmits();
const initialValues = ref({
    type: BucketTypeEnum.s3,
    endpoint: props.initialData?.endpoint || '',
    bucket_name: props.initialData?.bucket_name || '',
    access_key: props.initialData?.access_key || '',
    secret_key: props.initialData?.secret_key || '',
    session_token: props.initialData?.session_token || '',
    secure: props.initialData?.secure ?? true,
    region: props.initialData?.region || '',
});
watch(() => props.initialData, (data) => {
    if (data) {
        initialValues.value.endpoint = data.endpoint || '';
        initialValues.value.bucket_name = data.bucket_name || '';
        initialValues.value.access_key = data.access_key || '';
        initialValues.value.secret_key = data.secret_key || '';
        initialValues.value.session_token = data.session_token || '';
        initialValues.value.secure = data.secure ?? true;
        initialValues.value.region = data.region || '';
    }
});
const createBucketResolver = zodResolver(z.object({
    endpoint: z.string().min(1),
    bucket_name: z.string().min(1),
    access_key: z.string(),
    secret_key: z.string(),
    session_token: z.string(),
    region: z.string().min(1),
}));
const updateBucketResolver = zodResolver(z.object({
    endpoint: z.string().optional(),
    bucket_name: z.string().optional(),
    access_key: z.string().optional(),
    secret_key: z.string().optional(),
    session_token: z.string().optional(),
    region: z.string().optional(),
}));
const resolver = computed(() => (props.update ? updateBucketResolver : createBucketResolver));
function onSubmit({ valid }) {
    if (!valid)
        return;
    if (props.update) {
        const formData = {
            type: BucketTypeEnum.s3,
            endpoint: initialValues.value.endpoint || props.initialData?.endpoint || '',
            bucket_name: initialValues.value.bucket_name || props.initialData?.bucket_name || '',
            region: initialValues.value.region || props.initialData?.region || '',
            secure: initialValues.value.secure,
        };
        if (initialValues.value.access_key && initialValues.value.access_key.trim() !== '') {
            formData.access_key = initialValues.value.access_key;
        }
        if (initialValues.value.secret_key && initialValues.value.secret_key.trim() !== '') {
            formData.secret_key = initialValues.value.secret_key;
        }
        if (initialValues.value.session_token && initialValues.value.session_token.trim() !== '') {
            formData.session_token = initialValues.value.session_token;
        }
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
}));
const __VLS_2 = __VLS_1({
    ...{ 'onSubmit': {} },
    id: "bucketForm",
    initialValues: (__VLS_ctx.initialValues),
    resolver: (__VLS_ctx.resolver),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onSubmit) });
var __VLS_7;
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
        for: "endpoint",
        ...{ class: "label required" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    /** @type {__VLS_StyleScopedClasses['required']} */ ;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.InputText} */
    InputText;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        modelValue: (__VLS_ctx.initialValues.endpoint),
        id: "endpoint",
        name: "endpoint",
        type: "text",
        placeholder: "e.g. s3.amazonaws.com",
        fluid: true,
    }));
    const __VLS_11 = __VLS_10({
        modelValue: (__VLS_ctx.initialValues.endpoint),
        id: "endpoint",
        name: "endpoint",
        type: "text",
        placeholder: "e.g. s3.amazonaws.com",
        fluid: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    if ($form.endpoint?.invalid) {
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
        for: "bucket_name",
        ...{ class: "label required" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    /** @type {__VLS_StyleScopedClasses['required']} */ ;
    let __VLS_14;
    /** @ts-ignore @type { | typeof __VLS_components.InputText} */
    InputText;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        modelValue: (__VLS_ctx.initialValues.bucket_name),
        id: "bucket_name",
        name: "bucket_name",
        type: "text",
        placeholder: "e.g. luml-storage",
        fluid: true,
    }));
    const __VLS_16 = __VLS_15({
        modelValue: (__VLS_ctx.initialValues.bucket_name),
        id: "bucket_name",
        name: "bucket_name",
        type: "text",
        placeholder: "e.g. luml-storage",
        fluid: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
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
        for: "access_key",
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_19;
    /** @ts-ignore @type { | typeof __VLS_components.InputText} */
    InputText;
    // @ts-ignore
    const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
        modelValue: (__VLS_ctx.initialValues.access_key),
        id: "access_key",
        name: "access_key",
        type: "text",
        placeholder: "Enter access key",
        fluid: true,
    }));
    const __VLS_21 = __VLS_20({
        modelValue: (__VLS_ctx.initialValues.access_key),
        id: "access_key",
        name: "access_key",
        type: "text",
        placeholder: "Enter access key",
        fluid: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_20));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: "secret_key",
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_24;
    /** @ts-ignore @type { | typeof __VLS_components.InputText} */
    InputText;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
        modelValue: (__VLS_ctx.initialValues.secret_key),
        id: "secret_key",
        name: "secret_key",
        type: "text",
        placeholder: "Enter secret key",
        fluid: true,
    }));
    const __VLS_26 = __VLS_25({
        modelValue: (__VLS_ctx.initialValues.secret_key),
        id: "secret_key",
        name: "secret_key",
        type: "text",
        placeholder: "Enter secret key",
        fluid: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: "region",
        ...{ class: "label required" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    /** @type {__VLS_StyleScopedClasses['required']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        autoHide: (false),
    });
    __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { left: true, }, value: ('If your provider doesn’t require a region, you may enter any value.') }, null, null);
    let __VLS_29;
    /** @ts-ignore @type { | typeof __VLS_components.circleHelp | typeof __VLS_components.CircleHelp | typeof __VLS_components['circle-help']} */
    circleHelp;
    // @ts-ignore
    const __VLS_30 = __VLS_asFunctionalComponent1(__VLS_29, new __VLS_29({
        size: (15),
        ...{ class: "tooltip-icon" },
    }));
    const __VLS_31 = __VLS_30({
        size: (15),
        ...{ class: "tooltip-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_30));
    /** @type {__VLS_StyleScopedClasses['tooltip-icon']} */ ;
    let __VLS_34;
    /** @ts-ignore @type { | typeof __VLS_components.InputText} */
    InputText;
    // @ts-ignore
    const __VLS_35 = __VLS_asFunctionalComponent1(__VLS_34, new __VLS_34({
        modelValue: (__VLS_ctx.initialValues.region),
        id: "region",
        name: "region",
        type: "text",
        placeholder: "e.g. us-west-2",
        fluid: true,
    }));
    const __VLS_36 = __VLS_35({
        modelValue: (__VLS_ctx.initialValues.region),
        id: "region",
        name: "region",
        type: "text",
        placeholder: "e.g. us-west-2",
        fluid: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_35));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field field--protocol" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    /** @type {__VLS_StyleScopedClasses['field--protocol']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_39;
    /** @ts-ignore @type { | typeof __VLS_components.ToggleSwitch} */
    ToggleSwitch;
    // @ts-ignore
    const __VLS_40 = __VLS_asFunctionalComponent1(__VLS_39, new __VLS_39({
        modelValue: (__VLS_ctx.initialValues.secure),
        name: "secure",
    }));
    const __VLS_41 = __VLS_40({
        modelValue: (__VLS_ctx.initialValues.secure),
        name: "secure",
    }, ...__VLS_functionalComponentArgsRest(__VLS_40));
    if (__VLS_ctx.showSubmitButton) {
        let __VLS_44;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_45 = __VLS_asFunctionalComponent1(__VLS_44, new __VLS_44({
            type: "submit",
            fluid: true,
            rounded: true,
            loading: (__VLS_ctx.loading),
        }));
        const __VLS_46 = __VLS_45({
            type: "submit",
            fluid: true,
            rounded: true,
            loading: (__VLS_ctx.loading),
        }, ...__VLS_functionalComponentArgsRest(__VLS_45));
        const { default: __VLS_49 } = __VLS_47.slots;
        // @ts-ignore
        [initialValues, initialValues, initialValues, initialValues, initialValues, initialValues, initialValues, resolver, onSubmit, vTooltip, showSubmitButton, loading,];
        var __VLS_47;
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
