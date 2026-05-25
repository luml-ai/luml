/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { PermissionEnum, } from '@/lib/api/api.interfaces';
import { ref, watch } from 'vue';
import { Dialog, Button, InputText, Select, useToast, useConfirm, } from 'primevue';
import { Orbit } from 'lucide-vue-next';
import { Form } from '@primevue/forms';
import { z } from 'zod';
import { zodResolver } from '@primevue/forms/resolvers/zod';
import { useBucketsStore } from '@/stores/buckets';
import { useOrbitsStore } from '@/stores/orbits';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { deleteOrbitConfirmOptions } from '@/lib/primevue/data/confirm';
const dialogPT = {
    footer: {
        style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
    },
};
const resolver = zodResolver(z.object({
    name: z.string().min(1),
    bucket_secret_id: z.string(),
}));
const props = defineProps();
const visible = defineModel('visible');
const bucketsStore = useBucketsStore();
const orbitsStore = useOrbitsStore();
const toast = useToast();
const confirm = useConfirm();
const initialValues = ref({
    name: props.orbit.name,
    bucket_secret_id: props.orbit.bucket_secret_id,
});
const loading = ref(false);
async function saveChanges() {
    try {
        loading.value = true;
        const payload = {
            id: props.orbit.id,
            name: initialValues.value.name,
            bucket_secret_id: initialValues.value.bucket_secret_id,
        };
        await orbitsStore.updateOrbit(props.orbit.organization_id, payload);
        toast.add(simpleSuccessToast('Orbit info successfully updated'));
        visible.value = false;
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to update orbit'));
    }
    finally {
        loading.value = false;
    }
}
function onDeleteClick() {
    confirm.require(deleteOrbitConfirmOptions(deleteOrbit));
}
async function deleteOrbit() {
    try {
        loading.value = true;
        await orbitsStore.deleteOrbit(props.orbit.organization_id, props.orbit.id);
        toast.add(simpleSuccessToast('Orbit successfully deleted'));
        visible.value = false;
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to delete orbit'));
    }
    finally {
        loading.value = false;
    }
}
watch(visible, (val) => {
    val && bucketsStore.getBuckets(props.orbit.organization_id);
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
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
{
    const { header: __VLS_7 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "dialog-title" },
    });
    /** @type {__VLS_StyleScopedClasses['dialog-title']} */ ;
    let __VLS_8;
    /** @ts-ignore @type { | typeof __VLS_components.Orbit} */
    Orbit;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        size: (20),
        color: "var(--p-primary-color)",
    }));
    const __VLS_10 = __VLS_9({
        size: (20),
        color: "var(--p-primary-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [visible, dialogPT,];
}
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    ...{ 'onSubmit': {} },
    id: "orbit-edit-form",
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    ...{ class: "form" },
}));
const __VLS_15 = __VLS_14({
    ...{ 'onSubmit': {} },
    id: "orbit-edit-form",
    initialValues: __VLS_ctx.initialValues,
    resolver: __VLS_ctx.resolver,
    ...{ class: "form" },
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
let __VLS_18;
const __VLS_19 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.saveChanges) });
/** @type {__VLS_StyleScopedClasses['form']} */ ;
const { default: __VLS_20 } = __VLS_16.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form-item" },
});
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "name",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_21;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
    modelValue: (__VLS_ctx.initialValues.name),
    name: "name",
    id: "name",
}));
const __VLS_23 = __VLS_22({
    modelValue: (__VLS_ctx.initialValues.name),
    name: "name",
    id: "name",
}, ...__VLS_functionalComponentArgsRest(__VLS_22));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form-item" },
});
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "bucket",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_26;
/** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
    modelValue: (__VLS_ctx.initialValues.bucket_secret_id),
    disabled: true,
    options: (__VLS_ctx.bucketsStore.buckets),
    optionLabel: "bucket_name",
    optionValue: "id",
    name: "bucket_secret_id",
    id: "bucket",
}));
const __VLS_28 = __VLS_27({
    modelValue: (__VLS_ctx.initialValues.bucket_secret_id),
    disabled: true,
    options: (__VLS_ctx.bucketsStore.buckets),
    optionLabel: "bucket_name",
    optionValue: "id",
    name: "bucket_secret_id",
    id: "bucket",
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "message" },
});
/** @type {__VLS_StyleScopedClasses['message']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
    href: "mailto:contact@dataforce.solutions",
    ...{ class: "link" },
});
/** @type {__VLS_StyleScopedClasses['link']} */ ;
// @ts-ignore
[initialValues, initialValues, initialValues, resolver, saveChanges, bucketsStore,];
var __VLS_16;
var __VLS_17;
{
    const { footer: __VLS_31 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    if (__VLS_ctx.orbit.permissions.orbit.includes(__VLS_ctx.PermissionEnum.delete)) {
        let __VLS_32;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
            ...{ 'onClick': {} },
            variant: "outlined",
            severity: "warn",
            disabled: (__VLS_ctx.loading),
        }));
        const __VLS_34 = __VLS_33({
            ...{ 'onClick': {} },
            variant: "outlined",
            severity: "warn",
            disabled: (__VLS_ctx.loading),
        }, ...__VLS_functionalComponentArgsRest(__VLS_33));
        let __VLS_37;
        const __VLS_38 = ({ click: {} },
            { onClick: (__VLS_ctx.onDeleteClick) });
        const { default: __VLS_39 } = __VLS_35.slots;
        // @ts-ignore
        [orbit, PermissionEnum, loading, onDeleteClick,];
        var __VLS_35;
        var __VLS_36;
    }
    let __VLS_40;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
        type: "submit",
        loading: (__VLS_ctx.loading),
        form: "orbit-edit-form",
    }));
    const __VLS_42 = __VLS_41({
        type: "submit",
        loading: (__VLS_ctx.loading),
        form: "orbit-edit-form",
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    const { default: __VLS_45 } = __VLS_43.slots;
    // @ts-ignore
    [loading,];
    var __VLS_43;
    // @ts-ignore
    [];
}
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
