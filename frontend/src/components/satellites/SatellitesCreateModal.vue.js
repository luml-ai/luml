/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Dialog, InputText, Button, Textarea, useToast } from 'primevue';
import { Form } from '@primevue/forms';
import { ref, watch } from 'vue';
import { useSatellitesStore } from '@/stores/satellites';
import { useRoute } from 'vue-router';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { satellitesResolver } from '@/utils/forms/resolvers';
const emits = defineEmits();
const dialogPt = {
    root: {
        style: 'max-width: 500px; width: 100%;',
    },
    header: {
        style: 'padding: 28px; text-transform: uppercase; font-size: 20px;',
    },
    content: {
        style: 'padding: 0 28px 28px;',
    },
};
const visible = defineModel('visible');
const satellitesStore = useSatellitesStore();
const route = useRoute();
const toast = useToast();
const initialValues = ref({
    name: '',
    description: '',
});
const loading = ref(false);
async function onSubmit({ valid }) {
    if (!valid)
        return;
    const organizationIdParam = route.params.organizationId;
    const orbitIdParam = route.params.id;
    const organizationId = typeof organizationIdParam === 'string' ? organizationIdParam : organizationIdParam?.[0];
    const orbitId = typeof orbitIdParam === 'string' ? orbitIdParam : orbitIdParam?.[0];
    try {
        if (!organizationId) {
            throw new Error('Current organization was not found');
        }
        if (!orbitId) {
            throw new Error('Current orbit was not found');
        }
        loading.value = true;
        const data = await satellitesStore.createSatellite(organizationId, orbitId, initialValues.value);
        emits('create', data);
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.detail?.message || e?.message || 'Failed to create satellite'));
    }
    finally {
        loading.value = false;
    }
}
watch(visible, (val) => {
    if (!val) {
        initialValues.value.name = '';
        initialValues.value.description = '';
    }
});
let __VLS_modelEmit;
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
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    visible: (__VLS_ctx.visible),
    header: "Connect a new satellite",
    pt: (__VLS_ctx.dialogPt),
    modal: true,
    draggable: (false),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    header: "Connect a new satellite",
    pt: (__VLS_ctx.dialogPt),
    modal: true,
    draggable: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
let __VLS_7;
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
    ...{ 'onSubmit': {} },
    resolver: (__VLS_ctx.satellitesResolver),
    initialValues: (__VLS_ctx.initialValues),
}));
const __VLS_9 = __VLS_8({
    ...{ 'onSubmit': {} },
    resolver: (__VLS_ctx.satellitesResolver),
    initialValues: (__VLS_ctx.initialValues),
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
let __VLS_12;
const __VLS_13 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onSubmit) });
const { default: __VLS_14 } = __VLS_10.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "fields" },
});
/** @type {__VLS_StyleScopedClasses['fields']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "name",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_15;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    modelValue: (__VLS_ctx.initialValues.name),
    id: "name",
    name: "name",
    type: "text",
    placeholder: "Name your satellite",
    fluid: true,
}));
const __VLS_17 = __VLS_16({
    modelValue: (__VLS_ctx.initialValues.name),
    id: "name",
    name: "name",
    type: "text",
    placeholder: "Name your satellite",
    fluid: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "description",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.Textarea | typeof __VLS_components.Textarea} */
Textarea;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    modelValue: (__VLS_ctx.initialValues.description),
    id: "description",
    name: "description",
    placeholder: "Describe your satellite",
    fluid: true,
    ...{ class: "textarea" },
}));
const __VLS_22 = __VLS_21({
    modelValue: (__VLS_ctx.initialValues.description),
    id: "description",
    name: "description",
    placeholder: "Describe your satellite",
    fluid: true,
    ...{ class: "textarea" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
/** @type {__VLS_StyleScopedClasses['textarea']} */ ;
let __VLS_25;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
    label: "Create",
    fluid: true,
    rounded: true,
    type: "submit",
}));
const __VLS_27 = __VLS_26({
    label: "Create",
    fluid: true,
    rounded: true,
    type: "submit",
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
// @ts-ignore
[visible, dialogPt, satellitesResolver, initialValues, initialValues, initialValues, onSubmit,];
var __VLS_10;
var __VLS_11;
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
