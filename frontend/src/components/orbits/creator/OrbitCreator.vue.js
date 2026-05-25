/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Dialog, Button, InputText, Checkbox, MultiSelect, Select, useToast } from 'primevue';
import { Form } from '@primevue/forms';
import { computed, ref, watch } from 'vue';
import { useOrganizationStore } from '@/stores/organization';
import { OrbitRoleEnum } from '../orbits.interfaces';
import { useBucketsStore } from '@/stores/buckets';
import { Plus } from 'lucide-vue-next';
import { useOrbitsStore } from '@/stores/orbits';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { useUserStore } from '@/stores/user';
import { orbitCreatorResolver } from '@/utils/forms/resolvers';
const emit = defineEmits();
const props = defineProps();
const dialogPt = {
    root: {
        style: 'max-width: 500px; width: 100%;',
    },
    header: {
        style: 'padding: 28px;',
    },
    content: {
        style: 'padding: 0 28px 28px;',
    },
};
const multiSelectPt = {
    pcFilter: {
        root: {
            class: 'p-inputtext-sm p-inputfield-sm',
        },
    },
    overlay: {
        style: 'max-width: 442px; overflow: hidden;',
    },
    optionLabel: {
        style: 'overflow: hidden; text-overflow: ellipsis;',
    },
    label: {
        style: 'display: flex; flex-wrap: nowrap; overflow-x: auto',
    },
};
const memberRoleOptions = [OrbitRoleEnum.admin, OrbitRoleEnum.member];
const organizationStore = useOrganizationStore();
const bucketsStore = useBucketsStore();
const orbitsStore = useOrbitsStore();
const toast = useToast();
const userStore = useUserStore();
const membersList = computed(() => {
    if (!organizationStore.organizationDetails)
        return [];
    return organizationStore.organizationDetails.members
        .map((member) => member.user)
        .filter((user) => user.id !== userStore.getUserId);
});
const visible = defineModel('visible');
const resolver = orbitCreatorResolver(orbitsStore.orbitsList);
const initialValues = ref({
    name: '',
    members: [],
    bucket_secret_id: undefined,
    notify: true,
});
const loading = ref(false);
const membersModel = ref([]);
const getMemberFullName = computed(() => (userId) => {
    return membersList.value.find((member) => member.id === userId)?.full_name || '';
});
watch(membersModel, (members) => {
    initialValues.value.members = members.map((member) => {
        const includedMember = initialValues.value.members?.find((m) => m.user_id === member.id);
        return includedMember || { user_id: member.id, role: OrbitRoleEnum.member };
    });
}, { deep: true });
async function onSubmit({ valid }) {
    if (!valid)
        return;
    try {
        loading.value = true;
        const payload = initialValues.value;
        const orbit = await orbitsStore.createOrbit(props.organizationId, payload);
        toast.add(simpleSuccessToast('Orbit created'));
        if (orbit)
            emit('created', orbit);
        visible.value = false;
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to create orbit'));
    }
    finally {
        loading.value = false;
    }
}
watch(visible, (val) => {
    if (val)
        bucketsStore.getBuckets(props.organizationId);
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
    header: "CREATE A NEW ORBIT",
    modal: true,
    draggable: (false),
    pt: (__VLS_ctx.dialogPt),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    header: "CREATE A NEW ORBIT",
    modal: true,
    draggable: (false),
    pt: (__VLS_ctx.dialogPt),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
let __VLS_7;
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
    ...{ 'onSubmit': {} },
    initialValues: (__VLS_ctx.initialValues),
    resolver: (__VLS_ctx.resolver),
    validateOnValueUpdate: (false),
}));
const __VLS_9 = __VLS_8({
    ...{ 'onSubmit': {} },
    initialValues: (__VLS_ctx.initialValues),
    resolver: (__VLS_ctx.resolver),
    validateOnValueUpdate: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
let __VLS_12;
const __VLS_13 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onSubmit) });
const { default: __VLS_14 } = __VLS_10.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "inputs" },
});
/** @type {__VLS_StyleScopedClasses['inputs']} */ ;
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
    placeholder: "e.g. Data Science Core, Growth Experiments",
    fluid: true,
}));
const __VLS_17 = __VLS_16({
    modelValue: (__VLS_ctx.initialValues.name),
    id: "name",
    name: "name",
    placeholder: "e.g. Data Science Core, Growth Experiments",
    fluid: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "members",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.MultiSelect} */
MultiSelect;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    modelValue: (__VLS_ctx.membersModel),
    options: (__VLS_ctx.membersList),
    optionLabel: "full_name",
    display: "chip",
    filter: true,
    id: "members",
    placeholder: "Select members to add to this Orbit",
    fluid: true,
    pt: (__VLS_ctx.multiSelectPt),
}));
const __VLS_22 = __VLS_21({
    modelValue: (__VLS_ctx.membersModel),
    options: (__VLS_ctx.membersList),
    optionLabel: "full_name",
    display: "chip",
    filter: true,
    id: "members",
    placeholder: "Select members to add to this Orbit",
    fluid: true,
    pt: (__VLS_ctx.multiSelectPt),
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
if (__VLS_ctx.membersModel.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "members" },
    });
    /** @type {__VLS_StyleScopedClasses['members']} */ ;
    for (const [member] of __VLS_vFor((__VLS_ctx.initialValues.members))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (member.user_id),
            ...{ class: "member" },
        });
        /** @type {__VLS_StyleScopedClasses['member']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "member-name" },
        });
        /** @type {__VLS_StyleScopedClasses['member-name']} */ ;
        (__VLS_ctx.getMemberFullName(member.user_id));
        let __VLS_25;
        /** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
        Select;
        // @ts-ignore
        const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
            modelValue: (member.role),
            options: (__VLS_ctx.memberRoleOptions),
            size: "small",
        }));
        const __VLS_27 = __VLS_26({
            modelValue: (member.role),
            options: (__VLS_ctx.memberRoleOptions),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_26));
        // @ts-ignore
        [visible, dialogPt, initialValues, initialValues, initialValues, resolver, onSubmit, membersModel, membersModel, membersList, multiSelectPt, getMemberFullName, memberRoleOptions,];
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "bucket",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_30;
/** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
    modelValue: (__VLS_ctx.initialValues.bucket_secret_id),
    name: "bucket_secret_id",
    options: (__VLS_ctx.bucketsStore.buckets),
    optionLabel: "bucket_name",
    optionValue: "id",
    filter: true,
    id: "bucket",
    placeholder: "Select a storage bucket for this Orbit",
    fluid: true,
    pt: (__VLS_ctx.multiSelectPt),
}));
const __VLS_32 = __VLS_31({
    modelValue: (__VLS_ctx.initialValues.bucket_secret_id),
    name: "bucket_secret_id",
    options: (__VLS_ctx.bucketsStore.buckets),
    optionLabel: "bucket_name",
    optionValue: "id",
    filter: true,
    id: "bucket",
    placeholder: "Select a storage bucket for this Orbit",
    fluid: true,
    pt: (__VLS_ctx.multiSelectPt),
}, ...__VLS_functionalComponentArgsRest(__VLS_31));
const { default: __VLS_35 } = __VLS_33.slots;
{
    const { footer: __VLS_36 } = __VLS_33.slots;
    if (!__VLS_ctx.bucketsStore.buckets.length) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "select-footer" },
        });
        /** @type {__VLS_StyleScopedClasses['select-footer']} */ ;
        let __VLS_37;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
            variant: "text",
            asChild: true,
            size: "small",
        }));
        const __VLS_39 = __VLS_38({
            variant: "text",
            asChild: true,
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_38));
        {
            const { default: __VLS_42 } = __VLS_40.slots;
            const [slotProps] = __VLS_vSlot(__VLS_42);
            let __VLS_43;
            /** @ts-ignore @type { | typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
            RouterLink;
            // @ts-ignore
            const __VLS_44 = __VLS_asFunctionalComponent1(__VLS_43, new __VLS_43({
                to: ({
                    name: 'organization-buckets',
                    params: { id: __VLS_ctx.organizationId },
                }),
                ...{ class: (slotProps.class) },
            }));
            const __VLS_45 = __VLS_44({
                to: ({
                    name: 'organization-buckets',
                    params: { id: __VLS_ctx.organizationId },
                }),
                ...{ class: (slotProps.class) },
            }, ...__VLS_functionalComponentArgsRest(__VLS_44));
            const { default: __VLS_48 } = __VLS_46.slots;
            let __VLS_49;
            /** @ts-ignore @type { | typeof __VLS_components.Plus} */
            Plus;
            // @ts-ignore
            const __VLS_50 = __VLS_asFunctionalComponent1(__VLS_49, new __VLS_49({
                size: (14),
            }));
            const __VLS_51 = __VLS_50({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_50));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            // @ts-ignore
            [initialValues, multiSelectPt, bucketsStore, bucketsStore, organizationId,];
            var __VLS_46;
            // @ts-ignore
            [];
            __VLS_40.slots['' /* empty slot name completion */];
        }
        var __VLS_40;
    }
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_33;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "checkbox" },
});
/** @type {__VLS_StyleScopedClasses['checkbox']} */ ;
let __VLS_54;
/** @ts-ignore @type { | typeof __VLS_components.Checkbox} */
Checkbox;
// @ts-ignore
const __VLS_55 = __VLS_asFunctionalComponent1(__VLS_54, new __VLS_54({
    modelValue: (__VLS_ctx.initialValues.notify),
    inputId: "notify",
    binary: true,
}));
const __VLS_56 = __VLS_55({
    modelValue: (__VLS_ctx.initialValues.notify),
    inputId: "notify",
    binary: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_55));
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "notify",
    ...{ class: "checkbox-label" },
});
/** @type {__VLS_StyleScopedClasses['checkbox-label']} */ ;
let __VLS_59;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_60 = __VLS_asFunctionalComponent1(__VLS_59, new __VLS_59({
    type: "submit",
    fluid: true,
    rounded: true,
    loading: (__VLS_ctx.loading),
}));
const __VLS_61 = __VLS_60({
    type: "submit",
    fluid: true,
    rounded: true,
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_60));
const { default: __VLS_64 } = __VLS_62.slots;
// @ts-ignore
[initialValues, loading,];
var __VLS_62;
// @ts-ignore
[];
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
