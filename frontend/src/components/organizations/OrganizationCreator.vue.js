/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { InputText, Button, Avatar } from 'primevue';
import { computed, reactive, ref } from 'vue';
import { Form } from '@primevue/forms';
import { zodResolver } from '@primevue/forms/resolvers/zod';
import { z } from 'zod';
import { useOrganizationStore } from '@/stores/organization';
import { useToast } from 'primevue';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
const emits = defineEmits();
const organizationStore = useOrganizationStore();
const toast = useToast();
const resolver = zodResolver(z.object({
    name: z.string().min(3),
}));
const logo = ref(null);
const loading = ref(false);
const initialValues = reactive({
    name: '',
});
const avatarLabel = computed(() => {
    return initialValues.name.charAt(0).toUpperCase();
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
        await organizationStore.createOrganization(payload);
        toast.add(simpleSuccessToast('All changes have been saved.'));
        emits('close');
    }
    catch (e) {
        toast.add(simpleErrorToast(e.message || 'Could not create organization'));
    }
    finally {
        loading.value = false;
    }
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content" },
});
/** @type {__VLS_StyleScopedClasses['content']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Avatar} */
Avatar;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    size: "xlarge",
    label: (__VLS_ctx.avatarLabel),
}));
const __VLS_2 = __VLS_1({
    size: "xlarge",
    label: (__VLS_ctx.avatarLabel),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onSubmit': {} },
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    ...{ class: "body" },
}));
const __VLS_7 = __VLS_6({
    ...{ 'onSubmit': {} },
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    ...{ class: "body" },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onFormSubmit) });
/** @type {__VLS_StyleScopedClasses['body']} */ ;
const { default: __VLS_12 } = __VLS_8.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "name",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    modelValue: (__VLS_ctx.initialValues.name),
    name: "name",
    id: "name",
    ...{ class: "input" },
}));
const __VLS_15 = __VLS_14({
    modelValue: (__VLS_ctx.initialValues.name),
    name: "name",
    id: "name",
    ...{ class: "input" },
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
/** @type {__VLS_StyleScopedClasses['input']} */ ;
let __VLS_18;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
    type: "submit",
    rounded: true,
    fluid: true,
    loading: (__VLS_ctx.loading),
}));
const __VLS_20 = __VLS_19({
    type: "submit",
    rounded: true,
    fluid: true,
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_19));
const { default: __VLS_23 } = __VLS_21.slots;
// @ts-ignore
[avatarLabel, initialValues, initialValues, resolver, onFormSubmit, loading,];
var __VLS_21;
// @ts-ignore
[];
var __VLS_8;
var __VLS_9;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
});
export default {};
