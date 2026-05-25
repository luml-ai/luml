/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { BucketTypeEnum, } from '@/lib/api/bucket-secrets/interfaces';
import { computed, ref } from 'vue';
import { Button, Dialog, useConfirm, useToast } from 'primevue';
import { BucketValidationError, useBucketsStore } from '@/stores/buckets';
import { Bolt } from 'lucide-vue-next';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { deleteBucketConfirmOptions } from '@/lib/primevue/data/confirm';
import S3BucketForm from './S3BucketForm.vue';
import AzureBucketForm from './AzureBucketForm.vue';
import ConnectedOrbitsList from './connected-orbits/ConnectedOrbitsList.vue';
const dialogPT = {
    footer: {
        class: 'organization-edit-footer',
    },
};
const props = defineProps();
const bucketsStore = useBucketsStore();
const confirm = useConfirm();
const toast = useToast();
const visible = ref(false);
const loading = ref(false);
const initialData = computed(() => {
    switch (props.bucket.type) {
        case BucketTypeEnum.s3:
            return {
                type: BucketTypeEnum.s3,
                bucket_name: props.bucket.bucket_name,
                endpoint: props.bucket.endpoint,
                region: props.bucket.region,
                secure: props.bucket.secure,
                access_key: '',
                secret_key: '',
            };
        case BucketTypeEnum.azure:
            return {
                type: BucketTypeEnum.azure,
                bucket_name: props.bucket.bucket_name,
                endpoint: props.bucket.endpoint,
            };
        default:
            throw new Error(`Invalid bucket type: ${props.bucket?.type}`);
    }
});
async function onFormSubmit(formData) {
    try {
        loading.value = true;
        await bucketsStore.checkExistingBucket(props.bucket.organization_id, props.bucket.id, formData);
        await bucketsStore.updateBucket(props.bucket.organization_id, props.bucket.id, {
            ...formData,
            id: props.bucket.id,
        });
        toast.add(simpleSuccessToast('Bucket has been updated.'));
        visible.value = false;
    }
    catch (err) {
        if (err instanceof BucketValidationError) {
            toast.add(simpleErrorToast(err.getMessage()));
        }
        else {
            toast.add(simpleErrorToast(err?.response?.data?.detail || err.message || 'Failed to update bucket'));
        }
    }
    finally {
        loading.value = false;
    }
}
function onDelete() {
    confirm.require(deleteBucketConfirmOptions(deleteBucket));
}
async function deleteBucket() {
    try {
        visible.value = false;
        loading.value = true;
        await bucketsStore.deleteBucket(props.bucket.organization_id, props.bucket.id);
        toast.add(simpleSuccessToast(`Bucket “${props.bucket.bucket_name}” was deleted.`));
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to delete bucket'));
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
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    severity: "secondary",
    variant: "text",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    severity: "secondary",
    variant: "text",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.visible = true;
            // @ts-ignore
            [visible,];
        } });
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { icon: __VLS_8 } = __VLS_3.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.Bolt} */
    Bolt;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        size: (14),
    }));
    const __VLS_11 = __VLS_10({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
let __VLS_14;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
    visible: (__VLS_ctx.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}));
const __VLS_16 = __VLS_15({
    visible: (__VLS_ctx.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
const { default: __VLS_19 } = __VLS_17.slots;
{
    const { header: __VLS_20 } = __VLS_17.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "popup-title" },
    });
    /** @type {__VLS_StyleScopedClasses['popup-title']} */ ;
    let __VLS_21;
    /** @ts-ignore @type { | typeof __VLS_components.Bolt} */
    Bolt;
    // @ts-ignore
    const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
        size: (20),
        ...{ class: "popup-title-icon" },
    }));
    const __VLS_23 = __VLS_22({
        size: (20),
        ...{ class: "popup-title-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_22));
    /** @type {__VLS_StyleScopedClasses['popup-title-icon']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [visible, dialogPT,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "dialog-content" },
});
/** @type {__VLS_StyleScopedClasses['dialog-content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bucket-form-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['bucket-form-wrapper']} */ ;
if (__VLS_ctx.initialData.type === __VLS_ctx.BucketTypeEnum.s3) {
    const __VLS_26 = S3BucketForm;
    // @ts-ignore
    const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
        ...{ 'onSubmit': {} },
        initialData: __VLS_ctx.initialData,
        loading: (__VLS_ctx.loading),
        showSubmitButton: (false),
        update: true,
    }));
    const __VLS_28 = __VLS_27({
        ...{ 'onSubmit': {} },
        initialData: __VLS_ctx.initialData,
        loading: (__VLS_ctx.loading),
        showSubmitButton: (false),
        update: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_27));
    let __VLS_31;
    const __VLS_32 = ({ submit: {} },
        { onSubmit: (__VLS_ctx.onFormSubmit) });
    var __VLS_29;
    var __VLS_30;
}
else {
    const __VLS_33 = AzureBucketForm;
    // @ts-ignore
    const __VLS_34 = __VLS_asFunctionalComponent1(__VLS_33, new __VLS_33({
        ...{ 'onSubmit': {} },
        initialData: __VLS_ctx.initialData,
        loading: (__VLS_ctx.loading),
        showSubmitButton: (false),
        update: true,
    }));
    const __VLS_35 = __VLS_34({
        ...{ 'onSubmit': {} },
        initialData: __VLS_ctx.initialData,
        loading: (__VLS_ctx.loading),
        showSubmitButton: (false),
        update: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_34));
    let __VLS_38;
    const __VLS_39 = ({ submit: {} },
        { onSubmit: (__VLS_ctx.onFormSubmit) });
    var __VLS_36;
    var __VLS_37;
}
if (props.bucket.orbits?.length) {
    const __VLS_40 = ConnectedOrbitsList;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
        orbits: (props.bucket.orbits),
    }));
    const __VLS_42 = __VLS_41({
        orbits: (props.bucket.orbits),
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
}
{
    const { footer: __VLS_45 } = __VLS_17.slots;
    let __VLS_46;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_47 = __VLS_asFunctionalComponent1(__VLS_46, new __VLS_46({
        ...{ 'onClick': {} },
        severity: "warn",
        variant: "outlined",
        disabled: (__VLS_ctx.loading),
    }));
    const __VLS_48 = __VLS_47({
        ...{ 'onClick': {} },
        severity: "warn",
        variant: "outlined",
        disabled: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_47));
    let __VLS_51;
    const __VLS_52 = ({ click: {} },
        { onClick: (__VLS_ctx.onDelete) });
    const { default: __VLS_53 } = __VLS_49.slots;
    // @ts-ignore
    [initialData, initialData, initialData, BucketTypeEnum, loading, loading, loading, onFormSubmit, onFormSubmit, onDelete,];
    var __VLS_49;
    var __VLS_50;
    let __VLS_54;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_55 = __VLS_asFunctionalComponent1(__VLS_54, new __VLS_54({
        type: "submit",
        disabled: (__VLS_ctx.loading),
        form: "bucketForm",
    }));
    const __VLS_56 = __VLS_55({
        type: "submit",
        disabled: (__VLS_ctx.loading),
        form: "bucketForm",
    }, ...__VLS_functionalComponentArgsRest(__VLS_55));
    const { default: __VLS_59 } = __VLS_57.slots;
    // @ts-ignore
    [loading,];
    var __VLS_57;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_17;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
