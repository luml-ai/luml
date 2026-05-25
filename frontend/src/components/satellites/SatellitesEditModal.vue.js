/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Dialog, InputText, Textarea, Button, useToast } from 'primevue';
import { Bolt } from 'lucide-vue-next';
import { computed, ref, watch } from 'vue';
import { Form } from '@primevue/forms';
import { satellitesResolver } from '@/utils/forms/resolvers';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { useSatellitesStore } from '@/stores/satellites';
import { useRoute } from 'vue-router';
import SatelliteDelete from './SatelliteDelete.vue';
const props = defineProps();
const toast = useToast();
const route = useRoute();
const satellitesStore = useSatellitesStore();
const dialogPT = {
    footer: {
        class: 'organization-edit-footer',
    },
};
const visible = defineModel('visible');
const deleteDialogVisible = ref(false);
const loading = ref(false);
const initialValues = ref({
    name: '',
    description: '',
});
const organizationId = computed(() => {
    const id = route.params.organizationId;
    if (!id || Array.isArray(id))
        throw new Error('Current organization was not found');
    return id;
});
const orbitId = computed(() => {
    const id = route.params.id;
    if (!id || Array.isArray(id))
        throw new Error('Current orbit was not found');
    return id;
});
async function onSubmit({ valid }) {
    if (!valid)
        return;
    try {
        loading.value = true;
        await satellitesStore.updateSatellite(organizationId.value, orbitId.value, props.data.id, initialValues.value);
        visible.value = false;
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || 'Failed to update satellite'));
    }
    finally {
        toast.add(simpleSuccessToast(`${props.data.name} updated successfully.`));
        loading.value = false;
    }
}
watch(visible, (val) => {
    if (val) {
        initialValues.value.name = props.data.name;
        initialValues.value.description = props.data.description;
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
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_3.slots;
{
    const { header: __VLS_6 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "popup-title" },
    });
    /** @type {__VLS_StyleScopedClasses['popup-title']} */ ;
    let __VLS_7;
    /** @ts-ignore @type { | typeof __VLS_components.Bolt} */
    Bolt;
    // @ts-ignore
    const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
        size: (20),
        color: "var(--p-primary-color)",
    }));
    const __VLS_9 = __VLS_8({
        size: (20),
        color: "var(--p-primary-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_8));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [visible, dialogPT,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "dialog-content" },
});
/** @type {__VLS_StyleScopedClasses['dialog-content']} */ ;
let __VLS_12;
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
    ...{ 'onSubmit': {} },
    id: "satellitesEditForm",
    initialValues: __VLS_ctx.initialValues,
    resolver: (__VLS_ctx.satellitesResolver),
}));
const __VLS_14 = __VLS_13({
    ...{ 'onSubmit': {} },
    id: "satellitesEditForm",
    initialValues: __VLS_ctx.initialValues,
    resolver: (__VLS_ctx.satellitesResolver),
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_17;
const __VLS_18 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onSubmit) });
const { default: __VLS_19 } = __VLS_15.slots;
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
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    modelValue: (__VLS_ctx.initialValues.name),
    id: "name",
    name: "name",
    type: "text",
    placeholder: "Name your satellite",
    fluid: true,
}));
const __VLS_22 = __VLS_21({
    modelValue: (__VLS_ctx.initialValues.name),
    id: "name",
    name: "name",
    type: "text",
    placeholder: "Name your satellite",
    fluid: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "description",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_25;
/** @ts-ignore @type { | typeof __VLS_components.Textarea | typeof __VLS_components.Textarea} */
Textarea;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
    modelValue: (__VLS_ctx.initialValues.description),
    id: "description",
    name: "description",
    placeholder: "Describe your satellite",
    fluid: true,
    ...{ class: "textarea" },
}));
const __VLS_27 = __VLS_26({
    modelValue: (__VLS_ctx.initialValues.description),
    id: "description",
    name: "description",
    placeholder: "Describe your satellite",
    fluid: true,
    ...{ class: "textarea" },
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
/** @type {__VLS_StyleScopedClasses['textarea']} */ ;
// @ts-ignore
[initialValues, initialValues, initialValues, satellitesResolver, onSubmit,];
var __VLS_15;
var __VLS_16;
{
    const { footer: __VLS_30 } = __VLS_3.slots;
    let __VLS_31;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
        ...{ 'onClick': {} },
        severity: "warn",
        variant: "outlined",
        disabled: (__VLS_ctx.loading),
    }));
    const __VLS_33 = __VLS_32({
        ...{ 'onClick': {} },
        severity: "warn",
        variant: "outlined",
        disabled: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_32));
    let __VLS_36;
    const __VLS_37 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.deleteDialogVisible = true;
                // @ts-ignore
                [loading, deleteDialogVisible,];
            } });
    const { default: __VLS_38 } = __VLS_34.slots;
    // @ts-ignore
    [];
    var __VLS_34;
    var __VLS_35;
    let __VLS_39;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_40 = __VLS_asFunctionalComponent1(__VLS_39, new __VLS_39({
        type: "submit",
        disabled: (__VLS_ctx.loading),
        form: "satellitesEditForm",
    }));
    const __VLS_41 = __VLS_40({
        type: "submit",
        disabled: (__VLS_ctx.loading),
        form: "satellitesEditForm",
    }, ...__VLS_functionalComponentArgsRest(__VLS_40));
    const { default: __VLS_44 } = __VLS_42.slots;
    // @ts-ignore
    [loading,];
    var __VLS_42;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
const __VLS_45 = SatelliteDelete;
// @ts-ignore
const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({
    visible: (__VLS_ctx.deleteDialogVisible),
    organizationId: (__VLS_ctx.organizationId),
    orbitId: (__VLS_ctx.orbitId),
    satelliteId: (props.data.id),
    name: (props.data.name),
}));
const __VLS_47 = __VLS_46({
    visible: (__VLS_ctx.deleteDialogVisible),
    organizationId: (__VLS_ctx.organizationId),
    orbitId: (__VLS_ctx.orbitId),
    satelliteId: (props.data.id),
    name: (props.data.name),
}, ...__VLS_functionalComponentArgsRest(__VLS_46));
// @ts-ignore
[deleteDialogVisible, organizationId, orbitId,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
