/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Button } from 'primevue';
import { Bolt } from 'lucide-vue-next';
import { ProviderStatus } from '@/lib/promt-fusion/prompt-fusion.interfaces';
import { computed, onBeforeMount, onUnmounted, ref } from 'vue';
import { LocalStorageService } from '@/utils/services/LocalStorageService';
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService';
import { getProviders } from '@/lib/promt-fusion/prompt-fusion.data';
import ProviderSettings from '@/components/express-tasks/prompt-fusion/step-main/control-center/providers/ProviderSettings.vue';
const props = defineProps();
const __VLS_emit = defineEmits();
const providers = ref(getProviders());
const openedProvider = ref(null);
const currentProvider = computed(() => {
    return providers.value.find((provider) => provider.id.toLowerCase() === props.providerId.toLowerCase());
});
function showProviderSettings() {
    if (!currentProvider.value)
        return;
    openedProvider.value = currentProvider.value;
}
function saveSettings(settings) {
    if (!openedProvider.value)
        return;
    const newStatus = getStatus(settings);
    openedProvider.value.status = newStatus;
    openedProvider.value.settings = settings;
    const settingsInStorage = LocalStorageService.get('providersSettings');
    promptFusionService.updateProviderSettings(openedProvider.value.id, settings);
    const isNeedToSaveData = settingsInStorage?.saveApiKeys;
    if (isNeedToSaveData) {
        saveSettingsInLocalStorage(settings, settingsInStorage, openedProvider.value.id);
    }
    openedProvider.value = null;
    promptFusionService.closeProviderSettings();
}
function getStatus(settings) {
    return settings.reduce((acc, setting) => {
        if (setting.required && !setting.value)
            return ProviderStatus.disconnected;
        return acc;
    }, ProviderStatus.connected);
}
function saveSettingsInLocalStorage(settings, settingsInStorage, provider) {
    const oldSettings = settingsInStorage || {};
    oldSettings[provider] = settings.reduce((acc, setting) => {
        acc[setting.id] = setting.value;
        return acc;
    }, {});
    LocalStorageService.set('providersSettings', oldSettings);
}
onBeforeMount(() => {
    if (!currentProvider.value)
        return;
    promptFusionService.updateProviderSettings(currentProvider.value.id, currentProvider.value.settings);
    promptFusionService.closeProviderSettings();
});
onUnmounted(() => {
    promptFusionService.resetState();
});
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
/** @type {__VLS_StyleScopedClasses['status']} */ ;
/** @type {__VLS_StyleScopedClasses['status--success']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "title" },
});
/** @type {__VLS_StyleScopedClasses['title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "buttons" },
});
/** @type {__VLS_StyleScopedClasses['buttons']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "provider" },
});
/** @type {__VLS_StyleScopedClasses['provider']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "provider-info" },
});
/** @type {__VLS_StyleScopedClasses['provider-info']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.img)({
    src: "@/assets/img/providers/open-ai.svg",
    alt: "",
    width: "20",
    height: "20",
});
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "status" },
    ...{ class: ({ 'status--success': __VLS_ctx.currentProvider?.status === __VLS_ctx.ProviderStatus.connected }) },
});
/** @type {__VLS_StyleScopedClasses['status']} */ ;
/** @type {__VLS_StyleScopedClasses['status--success']} */ ;
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
            __VLS_ctx.showProviderSettings();
            // @ts-ignore
            [currentProvider, ProviderStatus, showProviderSettings,];
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
/** @ts-ignore @type { | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
    ...{ 'onClick': {} },
    label: "finish",
}));
const __VLS_16 = __VLS_15({
    ...{ 'onClick': {} },
    label: "finish",
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
let __VLS_19;
const __VLS_20 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.$emit('finish');
            // @ts-ignore
            [$emit,];
        } });
var __VLS_17;
var __VLS_18;
if (__VLS_ctx.openedProvider) {
    const __VLS_21 = ProviderSettings;
    // @ts-ignore
    const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
        ...{ 'onSave': {} },
        ...{ 'onUpdate:modelValue': {} },
        modelValue: (!!__VLS_ctx.openedProvider),
        settings: (__VLS_ctx.openedProvider.settings),
        providerName: (__VLS_ctx.openedProvider.name),
    }));
    const __VLS_23 = __VLS_22({
        ...{ 'onSave': {} },
        ...{ 'onUpdate:modelValue': {} },
        modelValue: (!!__VLS_ctx.openedProvider),
        settings: (__VLS_ctx.openedProvider.settings),
        providerName: (__VLS_ctx.openedProvider.name),
    }, ...__VLS_functionalComponentArgsRest(__VLS_22));
    let __VLS_26;
    const __VLS_27 = ({ save: {} },
        { onSave: (__VLS_ctx.saveSettings) });
    const __VLS_28 = ({ 'update:modelValue': {} },
        { 'onUpdate:modelValue': (...[$event]) => {
                if (!(__VLS_ctx.openedProvider))
                    return;
                __VLS_ctx.openedProvider = null;
                // @ts-ignore
                [openedProvider, openedProvider, openedProvider, openedProvider, openedProvider, saveSettings,];
            } });
    var __VLS_24;
    var __VLS_25;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
