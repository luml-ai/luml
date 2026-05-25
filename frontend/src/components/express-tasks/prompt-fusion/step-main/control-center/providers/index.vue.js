/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ProviderStatus, } from '@/lib/promt-fusion/prompt-fusion.interfaces';
import { onBeforeMount, onBeforeUnmount, ref, watch } from 'vue';
import { getProviders } from '@/lib/promt-fusion/prompt-fusion.data';
import { LocalStorageService } from '@/utils/services/LocalStorageService';
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService';
import ProviderItem from './ProviderItem.vue';
import ProviderSettings from './ProviderSettings.vue';
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService';
const providers = ref(getProviders());
const visible = ref(false);
const openedProvider = ref(null);
const isProviderSettingsOpened = ref(false);
function saveSettings(settings) {
    if (!openedProvider.value)
        return;
    const newStatus = settings.reduce((acc, setting) => {
        if (setting.required && !setting.value)
            return ProviderStatus.disconnected;
        return acc;
    }, ProviderStatus.connected);
    openedProvider.value.status = newStatus;
    openedProvider.value.settings = settings;
    const settingsInStorage = LocalStorageService.get('providersSettings');
    promptFusionService.updateProviderSettings(openedProvider.value.id, settings);
    const isNeedToSaveData = settingsInStorage?.saveApiKeys;
    if (isNeedToSaveData) {
        settingsInStorage[openedProvider.value.id] = settings.reduce((acc, setting) => {
            acc[setting.id] = setting.value;
            return acc;
        }, {});
        LocalStorageService.set('providersSettings', settingsInStorage);
    }
    promptFusionService.closeProviderSettings();
}
function showSettings(provider) {
    openedProvider.value = provider;
    promptFusionService.closeSettings();
    isProviderSettingsOpened.value = true;
}
function onChangeSettingsStatus(open) {
    if (open) {
        visible.value = true;
    }
    else {
        visible.value = false;
    }
}
function onOpenProviderSettings(providerId) {
    const provider = providers.value.find((p) => p.id === providerId);
    if (provider)
        showSettings(provider);
}
function onCloseProviderSettings() {
    isProviderSettingsOpened.value = false;
    openedProvider.value = null;
    promptFusionService.openSettings();
}
function onProviderButtonClick() {
    AnalyticsService.track(AnalyticsTrackKeysEnum.choose_provider, { task: 'prompt_optimization' });
    promptFusionService.openSettings();
}
watch(isProviderSettingsOpened, (val) => {
    if (!val)
        promptFusionService.closeProviderSettings();
});
onBeforeMount(() => {
    promptFusionService.on('OPEN_PROVIDER_SETTINGS', onOpenProviderSettings);
    promptFusionService.on('CLOSE_PROVIDER_SETTINGS', onCloseProviderSettings);
    promptFusionService.on('CHANGE_SETTINGS_STATUS', onChangeSettingsStatus);
});
onBeforeUnmount(() => {
    promptFusionService.off('OPEN_PROVIDER_SETTINGS', onOpenProviderSettings);
    promptFusionService.off('CLOSE_PROVIDER_SETTINGS', onCloseProviderSettings);
    promptFusionService.off('CHANGE_SETTINGS_STATUS', onChangeSettingsStatus);
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
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
    { onClick: (__VLS_ctx.onProviderButtonClick) });
const { default: __VLS_7 } = __VLS_3.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.brain | typeof __VLS_components.Brain} */
brain;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    size: (14),
}));
const __VLS_10 = __VLS_9({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
// @ts-ignore
[onProviderButtonClick,];
var __VLS_3;
var __VLS_4;
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog'] | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog']} */
dDialog;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    visible: (__VLS_ctx.visible),
    modal: true,
    ...{ style: {} },
    dismissableMask: true,
}));
const __VLS_15 = __VLS_14({
    visible: (__VLS_ctx.visible),
    modal: true,
    ...{ style: {} },
    dismissableMask: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
const { default: __VLS_18 } = __VLS_16.slots;
{
    const { header: __VLS_19 } = __VLS_16.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "dialog-title" },
    });
    /** @type {__VLS_StyleScopedClasses['dialog-title']} */ ;
    // @ts-ignore
    [visible,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "providers" },
});
/** @type {__VLS_StyleScopedClasses['providers']} */ ;
for (const [provider] of __VLS_vFor((__VLS_ctx.providers))) {
    const __VLS_20 = ProviderItem;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
        provider: (provider),
    }));
    const __VLS_22 = __VLS_21({
        provider: (provider),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    // @ts-ignore
    [providers,];
}
// @ts-ignore
[];
var __VLS_16;
if (__VLS_ctx.openedProvider) {
    const __VLS_25 = ProviderSettings;
    // @ts-ignore
    const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
        ...{ 'onSave': {} },
        modelValue: (__VLS_ctx.isProviderSettingsOpened),
        settings: (__VLS_ctx.openedProvider.settings),
        providerName: (__VLS_ctx.openedProvider.name),
    }));
    const __VLS_27 = __VLS_26({
        ...{ 'onSave': {} },
        modelValue: (__VLS_ctx.isProviderSettingsOpened),
        settings: (__VLS_ctx.openedProvider.settings),
        providerName: (__VLS_ctx.openedProvider.name),
    }, ...__VLS_functionalComponentArgsRest(__VLS_26));
    let __VLS_30;
    const __VLS_31 = ({ save: {} },
        { onSave: (__VLS_ctx.saveSettings) });
    var __VLS_28;
    var __VLS_29;
}
// @ts-ignore
[openedProvider, openedProvider, openedProvider, isProviderSettingsOpened, saveSettings,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
