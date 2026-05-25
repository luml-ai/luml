/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useUserStore } from '@/stores/user';
import { storeToRefs } from 'pinia';
import { computed, ref, watch } from 'vue';
import UserSettings from './UserSettings.vue';
import UserChangePassword from './UserChangePassword.vue';
import UiThemeToggle from '../ui/UiThemeToggle.vue';
import { useAuthStore } from '@/stores/auth';
import { useThemeStore } from '@/stores/theme';
import { useToast } from 'primevue/usetoast';
import { passwordChangedSuccessToast } from '@/lib/primevue/data/toasts';
import UserInvitations from './UserInvitations.vue';
import ApiKeyModal from './ApiKeyModal.vue';
const userStore = useUserStore();
const authStore = useAuthStore();
const themeStore = useThemeStore();
const toast = useToast();
const theme = ref(themeStore.getCurrentTheme);
const showChangePasswordSuccess = () => {
    toast.add(passwordChangedSuccessToast);
};
const { getUserEmail, getUserFullName, getUserAvatar } = storeToRefs(userStore);
const mainButtonLabel = computed(() => getUserFullName.value || 'Account');
const isDialogVisible = ref(false);
const isApiKeyVisible = ref(false);
const menuItems = ref([
    {
        label: 'Account',
        action: () => {
            isSettingsPopupVisible.value = true;
        },
    },
    {
        label: 'Feedback',
        link: {
            target: '_blank',
            href: 'https://discord.com/invite/qVPPstSv9R',
        },
    },
    {
        label: 'Community',
        link: {
            target: '_blank',
            href: 'https://discord.com/invite/qVPPstSv9R',
        },
    },
    {
        label: 'API key',
        action: () => {
            isApiKeyVisible.value = true;
        },
    },
    {
        label: 'Appearance',
        themeToggle: true,
    },
]);
const isSettingsPopupVisible = ref(false);
const isChangePasswordPopupVisible = ref(false);
const toggleMenu = () => {
    isDialogVisible.value = !isDialogVisible.value;
};
const onButtonLogoutClick = async () => {
    await authStore.logout();
};
const onShowChangePassword = () => {
    isSettingsPopupVisible.value = false;
    isChangePasswordPopupVisible.value = true;
};
const onChangePasswordSuccess = () => {
    isSettingsPopupVisible.value = true;
    isChangePasswordPopupVisible.value = false;
    setTimeout(() => {
        showChangePasswordSuccess();
    }, 100);
};
watch(theme, () => {
    themeStore.changeTheme();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['user-open-button']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "wrapper" },
});
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "user-buttons" },
});
/** @type {__VLS_StyleScopedClasses['user-buttons']} */ ;
const __VLS_0 = UserInvitations || UserInvitations;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onClick': {} },
    severity: "help",
    ...{ class: "user-open-button" },
}));
const __VLS_7 = __VLS_6({
    ...{ 'onClick': {} },
    severity: "help",
    ...{ class: "user-open-button" },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = ({ click: {} },
    { onClick: (__VLS_ctx.toggleMenu) });
/** @type {__VLS_StyleScopedClasses['user-open-button']} */ ;
const { default: __VLS_12 } = __VLS_8.slots;
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.dAvatar | typeof __VLS_components.DAvatar | typeof __VLS_components['d-avatar'] | typeof __VLS_components.dAvatar | typeof __VLS_components.DAvatar | typeof __VLS_components['d-avatar']} */
dAvatar;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    label: (__VLS_ctx.getUserAvatar ? undefined : __VLS_ctx.mainButtonLabel[0]),
    image: (__VLS_ctx.getUserAvatar),
    shape: "circle",
}));
const __VLS_15 = __VLS_14({
    label: (__VLS_ctx.getUserAvatar ? undefined : __VLS_ctx.mainButtonLabel[0]),
    image: (__VLS_ctx.getUserAvatar),
    shape: "circle",
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
(__VLS_ctx.mainButtonLabel);
let __VLS_18;
/** @ts-ignore @type { | typeof __VLS_components.chevronDown | typeof __VLS_components.ChevronDown | typeof __VLS_components['chevron-down']} */
chevronDown;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
    size: (14),
}));
const __VLS_20 = __VLS_19({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_19));
// @ts-ignore
[toggleMenu, getUserAvatar, getUserAvatar, mainButtonLabel, mainButtonLabel,];
var __VLS_8;
var __VLS_9;
let __VLS_23;
/** @ts-ignore @type { | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog'] | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog']} */
dDialog;
// @ts-ignore
const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
    visible: (__VLS_ctx.isDialogVisible),
    position: "topright",
    closable: (false),
    draggable: (false),
    modal: true,
    dismissableMask: true,
    ...{ style: ({ marginTop: '85px' }) },
    ...{ class: "modal-transparent-mask" },
}));
const __VLS_25 = __VLS_24({
    visible: (__VLS_ctx.isDialogVisible),
    position: "topright",
    closable: (false),
    draggable: (false),
    modal: true,
    dismissableMask: true,
    ...{ style: ({ marginTop: '85px' }) },
    ...{ class: "modal-transparent-mask" },
}, ...__VLS_functionalComponentArgsRest(__VLS_24));
/** @type {__VLS_StyleScopedClasses['modal-transparent-mask']} */ ;
const { default: __VLS_28 } = __VLS_26.slots;
{
    const { header: __VLS_29 } = __VLS_26.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
        ...{ class: "header" },
    });
    /** @type {__VLS_StyleScopedClasses['header']} */ ;
    let __VLS_30;
    /** @ts-ignore @type { | typeof __VLS_components.dAvatar | typeof __VLS_components.DAvatar | typeof __VLS_components['d-avatar'] | typeof __VLS_components.dAvatar | typeof __VLS_components.DAvatar | typeof __VLS_components['d-avatar']} */
    dAvatar;
    // @ts-ignore
    const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
        label: (__VLS_ctx.getUserAvatar ? undefined : __VLS_ctx.getUserFullName?.[0] || __VLS_ctx.getUserEmail?.[0]),
        image: (__VLS_ctx.getUserAvatar),
        shape: "circle",
        size: "large",
    }));
    const __VLS_32 = __VLS_31({
        label: (__VLS_ctx.getUserAvatar ? undefined : __VLS_ctx.getUserFullName?.[0] || __VLS_ctx.getUserEmail?.[0]),
        image: (__VLS_ctx.getUserAvatar),
        shape: "circle",
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_31));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "user-info" },
    });
    /** @type {__VLS_StyleScopedClasses['user-info']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "user-name" },
    });
    /** @type {__VLS_StyleScopedClasses['user-name']} */ ;
    (__VLS_ctx.getUserFullName);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "user-email" },
    });
    /** @type {__VLS_StyleScopedClasses['user-email']} */ ;
    (__VLS_ctx.getUserEmail);
    // @ts-ignore
    [getUserAvatar, getUserAvatar, isDialogVisible, getUserFullName, getUserFullName, getUserEmail, getUserEmail,];
}
let __VLS_35;
/** @ts-ignore @type { | typeof __VLS_components.dMenu | typeof __VLS_components.DMenu | typeof __VLS_components['d-menu'] | typeof __VLS_components.dMenu | typeof __VLS_components.DMenu | typeof __VLS_components['d-menu']} */
dMenu;
// @ts-ignore
const __VLS_36 = __VLS_asFunctionalComponent1(__VLS_35, new __VLS_35({
    model: (__VLS_ctx.menuItems),
    ...{ style: ({ backgroundColor: 'transparent', border: 'none', padding: '0', minWidth: '228px' }) },
}));
const __VLS_37 = __VLS_36({
    model: (__VLS_ctx.menuItems),
    ...{ style: ({ backgroundColor: 'transparent', border: 'none', padding: '0', minWidth: '228px' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_36));
const { default: __VLS_40 } = __VLS_38.slots;
{
    const { item: __VLS_41 } = __VLS_38.slots;
    const [{ item, props }] = __VLS_vSlot(__VLS_41);
    if (item.themeToggle) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "appearance" },
        });
        /** @type {__VLS_StyleScopedClasses['appearance']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (item.label);
        const __VLS_42 = UiThemeToggle;
        // @ts-ignore
        const __VLS_43 = __VLS_asFunctionalComponent1(__VLS_42, new __VLS_42({
            modelValue: (__VLS_ctx.theme),
        }));
        const __VLS_44 = __VLS_43({
            modelValue: (__VLS_ctx.theme),
        }, ...__VLS_functionalComponentArgsRest(__VLS_43));
    }
    else if (item.link) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
            href: (item.link.href),
            target: (item.link.target),
            ...{ class: "menu-item" },
        });
        /** @type {__VLS_StyleScopedClasses['menu-item']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (item.label);
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (item.action) },
            type: "button",
            ...{ class: "menu-item" },
            ...(props.action),
        });
        /** @type {__VLS_StyleScopedClasses['menu-item']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (item.label);
    }
    // @ts-ignore
    [menuItems, theme,];
}
// @ts-ignore
[];
var __VLS_38;
{
    const { footer: __VLS_47 } = __VLS_26.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.footer, __VLS_intrinsics.footer)({
        ...{ class: "footer" },
    });
    /** @type {__VLS_StyleScopedClasses['footer']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.onButtonLogoutClick) },
        type: "button",
        ...{ class: "logout-button" },
    });
    /** @type {__VLS_StyleScopedClasses['logout-button']} */ ;
    // @ts-ignore
    [onButtonLogoutClick,];
}
// @ts-ignore
[];
var __VLS_26;
let __VLS_48;
/** @ts-ignore @type { | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog'] | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog']} */
dDialog;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent1(__VLS_48, new __VLS_48({
    visible: (__VLS_ctx.isSettingsPopupVisible),
    modal: true,
    ...{ style: ({ width: '37rem' }) },
}));
const __VLS_50 = __VLS_49({
    visible: (__VLS_ctx.isSettingsPopupVisible),
    modal: true,
    ...{ style: ({ width: '37rem' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
const { default: __VLS_53 } = __VLS_51.slots;
{
    const { header: __VLS_54 } = __VLS_51.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ style: {} },
    });
    // @ts-ignore
    [isSettingsPopupVisible,];
}
const __VLS_55 = UserSettings;
// @ts-ignore
const __VLS_56 = __VLS_asFunctionalComponent1(__VLS_55, new __VLS_55({
    ...{ 'onShowChangePassword': {} },
    ...{ 'onClose': {} },
}));
const __VLS_57 = __VLS_56({
    ...{ 'onShowChangePassword': {} },
    ...{ 'onClose': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_56));
let __VLS_60;
const __VLS_61 = ({ showChangePassword: {} },
    { onShowChangePassword: (__VLS_ctx.onShowChangePassword) });
const __VLS_62 = ({ close: {} },
    { onClose: (...[$event]) => {
            __VLS_ctx.isSettingsPopupVisible = !__VLS_ctx.isSettingsPopupVisible;
            // @ts-ignore
            [isSettingsPopupVisible, isSettingsPopupVisible, onShowChangePassword,];
        } });
var __VLS_58;
var __VLS_59;
// @ts-ignore
[];
var __VLS_51;
let __VLS_63;
/** @ts-ignore @type { | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog'] | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog']} */
dDialog;
// @ts-ignore
const __VLS_64 = __VLS_asFunctionalComponent1(__VLS_63, new __VLS_63({
    visible: (__VLS_ctx.isChangePasswordPopupVisible),
    modal: true,
    ...{ style: ({ width: '37rem' }) },
}));
const __VLS_65 = __VLS_64({
    visible: (__VLS_ctx.isChangePasswordPopupVisible),
    modal: true,
    ...{ style: ({ width: '37rem' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_64));
const { default: __VLS_68 } = __VLS_66.slots;
{
    const { header: __VLS_69 } = __VLS_66.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ style: {} },
    });
    // @ts-ignore
    [isChangePasswordPopupVisible,];
}
const __VLS_70 = UserChangePassword;
// @ts-ignore
const __VLS_71 = __VLS_asFunctionalComponent1(__VLS_70, new __VLS_70({
    ...{ 'onSuccess': {} },
}));
const __VLS_72 = __VLS_71({
    ...{ 'onSuccess': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_71));
let __VLS_75;
const __VLS_76 = ({ success: {} },
    { onSuccess: (__VLS_ctx.onChangePasswordSuccess) });
var __VLS_73;
var __VLS_74;
// @ts-ignore
[onChangePasswordSuccess,];
var __VLS_66;
const __VLS_77 = ApiKeyModal;
// @ts-ignore
const __VLS_78 = __VLS_asFunctionalComponent1(__VLS_77, new __VLS_77({
    show: (__VLS_ctx.isApiKeyVisible),
}));
const __VLS_79 = __VLS_78({
    show: (__VLS_ctx.isApiKeyVisible),
}, ...__VLS_functionalComponentArgsRest(__VLS_78));
// @ts-ignore
[isApiKeyVisible,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
