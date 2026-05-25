/// <reference types="../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { RouterView } from 'vue-router';
import AppTemplate from './templates/AppTemplate.vue';
import { onBeforeMount } from 'vue';
import { useThemeStore } from './stores/theme';
import { useAppScrollbarFix } from './hooks/useAppScrollbarFix';
import { DataProcessingWorker } from './lib/data-processing/DataProcessingWorker';
import UICustomToast from './components/ui/UICustomToast.vue';
const themeStore = useThemeStore();
useAppScrollbarFix();
onBeforeMount(() => {
    DataProcessingWorker.initPyodide();
    themeStore.checkTheme();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
const __VLS_0 = UICustomToast;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.dConfirmDialog | typeof __VLS_components.DConfirmDialog | typeof __VLS_components['d-confirm-dialog']} */
dConfirmDialog;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ style: {} },
}));
const __VLS_7 = __VLS_6({
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
const __VLS_10 = AppTemplate || AppTemplate;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({}));
const __VLS_12 = __VLS_11({}, ...__VLS_functionalComponentArgsRest(__VLS_11));
const { default: __VLS_15 } = __VLS_13.slots;
let __VLS_16;
/** @ts-ignore @type { | typeof __VLS_components.RouterView} */
RouterView;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({}));
const __VLS_18 = __VLS_17({}, ...__VLS_functionalComponentArgsRest(__VLS_17));
var __VLS_13;
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
