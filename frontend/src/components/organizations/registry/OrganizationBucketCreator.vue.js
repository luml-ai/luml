/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { BucketTypeEnum } from '@/lib/api/bucket-secrets/interfaces';
import { computed, ref } from 'vue';
import { Button, Dialog, useToast, SelectButton } from 'primevue';
import { Plus } from 'lucide-vue-next';
import { BucketValidationError, useBucketsStore } from '@/stores/buckets';
import { useOrganizationStore } from '@/stores/organization';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import AzureBucketForm from './AzureBucketForm.vue';
import S3BucketForm from './S3BucketForm.vue';
const dialogPT = {
    header: {
        style: 'padding: 28px;',
    },
    content: {
        style: 'padding: 0 28px 28px',
    },
};
const selectButtonOptions = [
    {
        label: 'S3 bucket',
        value: BucketTypeEnum.s3,
    },
    {
        label: 'Azure',
        value: BucketTypeEnum.azure,
    },
];
const organizationStore = useOrganizationStore();
const bucketsStore = useBucketsStore();
const toast = useToast();
const visible = ref(false);
const loading = ref(false);
const selectedBucketType = ref(BucketTypeEnum.s3);
const formComponent = computed(() => {
    return selectedBucketType.value === BucketTypeEnum.s3 ? S3BucketForm : AzureBucketForm;
});
async function create(data) {
    const organizationId = organizationStore.currentOrganization?.id;
    if (!organizationId) {
        toast.add(simpleErrorToast('Current organization not found'));
        return;
    }
    try {
        loading.value = true;
        await bucketsStore.checkBucket(data);
        await bucketsStore.createBucket(organizationId, data);
        visible.value = false;
        toast.add(simpleSuccessToast('New bucket has been added.'));
    }
    catch (e) {
        if (e instanceof BucketValidationError) {
            toast.add(simpleErrorToast(e.getMessage()));
        }
        else {
            toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to create bucket'));
        }
    }
    finally {
        loading.value = false;
    }
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.visible = true;
            // @ts-ignore
            [visible,];
        } });
const { default: __VLS_7 } = __VLS_3.slots;
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.Plus} */
Plus;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    size: (14),
}));
const __VLS_10 = __VLS_9({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    visible: (__VLS_ctx.visible),
    modal: true,
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}));
const __VLS_15 = __VLS_14({
    visible: (__VLS_ctx.visible),
    modal: true,
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
const { default: __VLS_18 } = __VLS_16.slots;
{
    const { header: __VLS_19 } = __VLS_16.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "creator-title" },
    });
    /** @type {__VLS_StyleScopedClasses['creator-title']} */ ;
    // @ts-ignore
    [visible, dialogPT,];
}
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.SelectButton | typeof __VLS_components.SelectButton} */
SelectButton;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    modelValue: (__VLS_ctx.selectedBucketType),
    options: (__VLS_ctx.selectButtonOptions),
    optionLabel: "label",
    optionValue: "value",
    ...{ class: "select-button" },
}));
const __VLS_22 = __VLS_21({
    modelValue: (__VLS_ctx.selectedBucketType),
    options: (__VLS_ctx.selectButtonOptions),
    optionLabel: "label",
    optionValue: "value",
    ...{ class: "select-button" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
/** @type {__VLS_StyleScopedClasses['select-button']} */ ;
const __VLS_25 = (__VLS_ctx.formComponent);
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
    ...{ 'onSubmit': {} },
    loading: (__VLS_ctx.loading),
    ...{ class: "form-component" },
}));
const __VLS_27 = __VLS_26({
    ...{ 'onSubmit': {} },
    loading: (__VLS_ctx.loading),
    ...{ class: "form-component" },
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
let __VLS_30;
const __VLS_31 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.create) });
/** @type {__VLS_StyleScopedClasses['form-component']} */ ;
var __VLS_28;
var __VLS_29;
// @ts-ignore
[selectedBucketType, selectButtonOptions, formComponent, loading, create,];
var __VLS_16;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
