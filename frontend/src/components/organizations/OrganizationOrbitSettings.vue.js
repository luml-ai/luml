/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref, watch } from 'vue';
import { useOrbitsStore } from '@/stores/orbits';
import { useOrganizationStore } from '@/stores/organization';
import { UserCog, Trash2 } from 'lucide-vue-next';
import { Dialog, AutoComplete, Button, useToast, Avatar, Select, useConfirm } from 'primevue';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { OrbitRoleEnum } from '../orbits/orbits.interfaces';
import { deleteUserConfirmOptions } from '@/lib/primevue/data/confirm';
import { useUserStore } from '@/stores/user';
const dialogPt = {
    root: {
        style: 'max-width: 800px; width: 100%;',
    },
    header: {
        style: 'padding: 36px 36px 12px; text-transform: uppercase; font-size: 20px; font-weight: 600;',
    },
    content: {
        style: 'padding: 0 36px 36px;',
    },
};
const OPTIONS = [
    {
        label: 'Admin',
        value: OrbitRoleEnum.admin,
    },
    {
        label: 'Member',
        value: OrbitRoleEnum.member,
    },
];
const props = defineProps();
const organizationsStore = useOrganizationStore();
const orbitsStore = useOrbitsStore();
const toast = useToast();
const confirm = useConfirm();
const userStore = useUserStore();
const visible = ref(false);
const loading = ref(false);
const initialOrbitMembers = ref([]);
const orbitMembers = ref([]);
const searchModel = ref([]);
const searchedMembers = ref([]);
const changedMembers = computed(() => orbitMembers.value.filter((member) => initialOrbitMembers.value.find((newMember) => newMember.id === member.id)?.role !==
    member.role));
function onComplete(event) {
    if (!organizationsStore.organizationDetails?.members?.length)
        return;
    searchedMembers.value = organizationsStore.organizationDetails.members.filter((member) => {
        if (orbitMembers.value.find((memberInOrbit) => memberInOrbit.id === member.id))
            return false;
        if (member.user.id === userStore.getUserId)
            return false;
        return (member.user.email.toLowerCase().includes(event.query.toLowerCase()) ||
            member.user.full_name.toLowerCase().includes(event.query.toLowerCase()));
    });
}
async function addUsers() {
    const organizationId = organizationsStore.organizationDetails?.id;
    if (!organizationId)
        return;
    const payloads = searchModel.value.map((member) => {
        return {
            role: OrbitRoleEnum.member,
            orbit_id: props.orbitId,
            user_id: member.user.id,
        };
    });
    try {
        const response = await Promise.all(payloads.map((payload) => orbitsStore.addMemberToOrbit(organizationId, payload)));
        orbitMembers.value = [...orbitMembers.value, ...response];
        toast.add(simpleSuccessToast('Users have been added to the organization'));
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to add user to orbit'));
    }
}
async function getOrbitDetails() {
    loading.value = true;
    const organizationId = organizationsStore.currentOrganization?.id;
    if (!organizationId)
        return;
    try {
        const details = await orbitsStore.getOrbitDetails(organizationId, props.orbitId);
        orbitMembers.value = details.members;
        initialOrbitMembers.value = JSON.parse(JSON.stringify(details.members));
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to load orbit details'));
    }
    finally {
        loading.value = false;
    }
}
function onTrashClick(memberId) {
    confirm.require(deleteUserConfirmOptions(() => deleteMember(memberId), 'You can add a user to your orbit at any time.'));
}
async function deleteMember(memberId) {
    try {
        loading.value = true;
        const organizationId = organizationsStore.currentOrganization?.id;
        if (!organizationId)
            throw new Error('Current organization not found');
        await orbitsStore.deleteMember(organizationId, props.orbitId, memberId);
        orbitMembers.value = orbitMembers.value.filter((member) => member.id !== memberId);
        initialOrbitMembers.value = initialOrbitMembers.value.filter((member) => member.id !== memberId);
        toast.add(simpleSuccessToast('The user has been successfully removed.'));
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e?.message));
    }
    finally {
        loading.value = false;
    }
}
async function saveChanges() {
    try {
        loading.value = true;
        const organizationId = organizationsStore.currentOrganization?.id;
        if (!organizationId)
            throw new Error('Current organization not found');
        const requests = changedMembers.value.map((member) => orbitsStore.updateMember(organizationId, props.orbitId, { id: member.id, role: member.role }));
        await Promise.all(requests);
        toast.add(simpleSuccessToast('Changes saved'));
        visible.value = false;
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e?.message));
    }
    finally {
        loading.value = false;
    }
}
watch(visible, (val) => {
    if (val) {
        getOrbitDetails();
    }
    else {
        orbitMembers.value = [];
        initialOrbitMembers.value = [];
    }
});
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['form']} */ ;
/** @type {__VLS_StyleScopedClasses['body']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    severity: "secondary",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    severity: "secondary",
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
    /** @ts-ignore @type { | typeof __VLS_components.UserCog} */
    UserCog;
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
    draggable: (false),
    modal: true,
    pt: (__VLS_ctx.dialogPt),
    header: "Manage Orbit Members",
}));
const __VLS_16 = __VLS_15({
    visible: (__VLS_ctx.visible),
    draggable: (false),
    modal: true,
    pt: (__VLS_ctx.dialogPt),
    header: "Manage Orbit Members",
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
const { default: __VLS_19 } = __VLS_17.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "dialog-content" },
});
/** @type {__VLS_StyleScopedClasses['dialog-content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text" },
});
/** @type {__VLS_StyleScopedClasses['text']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form" },
});
/** @type {__VLS_StyleScopedClasses['form']} */ ;
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.AutoComplete} */
AutoComplete;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.searchModel),
    placeholder: "Search users in organization",
    inputId: "multiple-ac-1",
    multiple: true,
    fluid: true,
    suggestions: (__VLS_ctx.searchedMembers),
    ...{ class: "autocomplete" },
    optionLabel: "user.email",
}));
const __VLS_22 = __VLS_21({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.searchModel),
    placeholder: "Search users in organization",
    inputId: "multiple-ac-1",
    multiple: true,
    fluid: true,
    suggestions: (__VLS_ctx.searchedMembers),
    ...{ class: "autocomplete" },
    optionLabel: "user.email",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
let __VLS_25;
const __VLS_26 = ({ complete: {} },
    { onComplete: (__VLS_ctx.onComplete) });
/** @type {__VLS_StyleScopedClasses['autocomplete']} */ ;
var __VLS_23;
var __VLS_24;
let __VLS_27;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_28 = __VLS_asFunctionalComponent1(__VLS_27, new __VLS_27({
    ...{ 'onClick': {} },
    severity: "secondary",
    disabled: (!__VLS_ctx.searchedMembers.length),
}));
const __VLS_29 = __VLS_28({
    ...{ 'onClick': {} },
    severity: "secondary",
    disabled: (!__VLS_ctx.searchedMembers.length),
}, ...__VLS_functionalComponentArgsRest(__VLS_28));
let __VLS_32;
const __VLS_33 = ({ click: {} },
    { onClick: (__VLS_ctx.addUsers) });
const { default: __VLS_34 } = __VLS_30.slots;
// @ts-ignore
[visible, dialogPt, searchModel, searchedMembers, searchedMembers, onComplete, addUsers,];
var __VLS_30;
var __VLS_31;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "body" },
});
/** @type {__VLS_StyleScopedClasses['body']} */ ;
if (!__VLS_ctx.orbitMembers.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "placeholder" },
    });
    /** @type {__VLS_StyleScopedClasses['placeholder']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "table-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['table-wrapper']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "table" },
    });
    /** @type {__VLS_StyleScopedClasses['table']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "table-header" },
    });
    /** @type {__VLS_StyleScopedClasses['table-header']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "table-row" },
    });
    /** @type {__VLS_StyleScopedClasses['table-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "table-body" },
    });
    /** @type {__VLS_StyleScopedClasses['table-body']} */ ;
    for (const [member] of __VLS_vFor((__VLS_ctx.orbitMembers))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "table-row" },
        });
        /** @type {__VLS_StyleScopedClasses['table-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell cell-user" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        /** @type {__VLS_StyleScopedClasses['cell-user']} */ ;
        let __VLS_35;
        /** @ts-ignore @type { | typeof __VLS_components.Avatar} */
        Avatar;
        // @ts-ignore
        const __VLS_36 = __VLS_asFunctionalComponent1(__VLS_35, new __VLS_35({
            label: (member.user.photo ? undefined : member.user.full_name[0]),
            shape: "circle",
            image: (member.user.photo),
            ...{ class: "avatar" },
        }));
        const __VLS_37 = __VLS_36({
            label: (member.user.photo ? undefined : member.user.full_name[0]),
            shape: "circle",
            image: (member.user.photo),
            ...{ class: "avatar" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_36));
        /** @type {__VLS_StyleScopedClasses['avatar']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({});
        (member.user.full_name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "cell" },
        });
        /** @type {__VLS_StyleScopedClasses['cell']} */ ;
        let __VLS_40;
        /** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
        Select;
        // @ts-ignore
        const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
            modelValue: (member.role),
            options: (__VLS_ctx.OPTIONS),
            optionLabel: "label",
            optionValue: "value",
            name: "role",
            id: "role",
            fluid: true,
        }));
        const __VLS_42 = __VLS_41({
            modelValue: (member.role),
            options: (__VLS_ctx.OPTIONS),
            optionLabel: "label",
            optionValue: "value",
            name: "role",
            id: "role",
            fluid: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_41));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "buttons" },
        });
        /** @type {__VLS_StyleScopedClasses['buttons']} */ ;
        let __VLS_45;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "outlined",
            disabled: (__VLS_ctx.loading),
        }));
        const __VLS_47 = __VLS_46({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "outlined",
            disabled: (__VLS_ctx.loading),
        }, ...__VLS_functionalComponentArgsRest(__VLS_46));
        let __VLS_50;
        const __VLS_51 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!!(!__VLS_ctx.orbitMembers.length))
                        return;
                    __VLS_ctx.onTrashClick(member.id);
                    // @ts-ignore
                    [orbitMembers, orbitMembers, OPTIONS, loading, onTrashClick,];
                } });
        const { default: __VLS_52 } = __VLS_48.slots;
        {
            const { icon: __VLS_53 } = __VLS_48.slots;
            let __VLS_54;
            /** @ts-ignore @type { | typeof __VLS_components.Trash2} */
            Trash2;
            // @ts-ignore
            const __VLS_55 = __VLS_asFunctionalComponent1(__VLS_54, new __VLS_54({
                size: (12),
            }));
            const __VLS_56 = __VLS_55({
                size: (12),
            }, ...__VLS_functionalComponentArgsRest(__VLS_55));
            // @ts-ignore
            [];
        }
        // @ts-ignore
        [];
        var __VLS_48;
        var __VLS_49;
        // @ts-ignore
        [];
    }
}
{
    const { footer: __VLS_59 } = __VLS_17.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "footer-buttons" },
    });
    /** @type {__VLS_StyleScopedClasses['footer-buttons']} */ ;
    let __VLS_60;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent1(__VLS_60, new __VLS_60({
        ...{ 'onClick': {} },
        type: "submit",
        disabled: (__VLS_ctx.loading || !__VLS_ctx.changedMembers.length),
        form: "editOrganizationForm",
    }));
    const __VLS_62 = __VLS_61({
        ...{ 'onClick': {} },
        type: "submit",
        disabled: (__VLS_ctx.loading || !__VLS_ctx.changedMembers.length),
        form: "editOrganizationForm",
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    let __VLS_65;
    const __VLS_66 = ({ click: {} },
        { onClick: (__VLS_ctx.saveChanges) });
    const { default: __VLS_67 } = __VLS_63.slots;
    // @ts-ignore
    [loading, changedMembers, saveChanges,];
    var __VLS_63;
    var __VLS_64;
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
