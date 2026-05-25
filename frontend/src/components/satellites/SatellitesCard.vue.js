/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { SatelliteStatusEnum } from '@/lib/api/satellites/interfaces';
import { getLastUpdateText } from '@/helpers/helpers';
import { EllipsisVertical, Rocket } from 'lucide-vue-next';
import { Button, Menu } from 'primevue';
import { computed, ref } from 'vue';
import SatellitesEditModal from './SatellitesEditModal.vue';
import SatellitesApiKeyModal from './SatellitesApiKeyModal.vue';
import UiId from '../ui/UiId.vue';
const props = defineProps();
const showEditModal = ref(false);
const showApiKey = ref(false);
const menu = ref();
const menuItems = ref([
    {
        label: 'Settings',
        command: () => {
            showEditModal.value = true;
        },
    },
    {
        label: 'API Key',
        command: () => {
            showApiKey.value = true;
        },
    },
]);
const updatedText = computed(() => {
    return getLastUpdateText(props.data.updated_at || props.data.created_at);
});
const statusData = computed(() => {
    switch (props.data.status) {
        case SatelliteStatusEnum.active:
            return { className: 'status--success', tooltip: 'Active satellite' };
        case SatelliteStatusEnum.error:
            return { className: 'status--warn', tooltip: 'The satellite appears to be offline' };
        case SatelliteStatusEnum.inactive:
            return { className: 'status--danger', tooltip: 'Not connected' };
        default:
            return { className: '', tooltip: '' };
    }
});
const toggle = (event) => {
    menu.value.toggle(event);
};
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
/** @type {__VLS_StyleScopedClasses['status']} */ ;
/** @type {__VLS_StyleScopedClasses['status--success']} */ ;
/** @type {__VLS_StyleScopedClasses['status--warn']} */ ;
/** @type {__VLS_StyleScopedClasses['status--danger']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card" },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content" },
});
/** @type {__VLS_StyleScopedClasses['content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "title" },
});
/** @type {__VLS_StyleScopedClasses['title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "status" },
    ...{ class: (__VLS_ctx.statusData.className) },
});
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { top: true, }, value: (__VLS_ctx.statusData.tooltip) }, null, null);
/** @type {__VLS_StyleScopedClasses['status']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
(__VLS_ctx.data.name);
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (__VLS_ctx.toggle) });
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { icon: __VLS_8 } = __VLS_3.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.EllipsisVertical} */
    EllipsisVertical;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        size: (14),
    }));
    const __VLS_11 = __VLS_10({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    // @ts-ignore
    [statusData, statusData, vTooltip, data, toggle,];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
let __VLS_14;
/** @ts-ignore @type { | typeof __VLS_components.Menu | typeof __VLS_components.Menu} */
Menu;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
    ref: "menu",
    model: (__VLS_ctx.menuItems),
    popup: (true),
    ...{ style: {} },
}));
const __VLS_16 = __VLS_15({
    ref: "menu",
    model: (__VLS_ctx.menuItems),
    popup: (true),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
var __VLS_19;
var __VLS_17;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "body" },
});
/** @type {__VLS_StyleScopedClasses['body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "id-row" },
});
/** @type {__VLS_StyleScopedClasses['id-row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "id-text" },
});
/** @type {__VLS_StyleScopedClasses['id-text']} */ ;
const __VLS_21 = UiId || UiId;
// @ts-ignore
const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
    id: (__VLS_ctx.data.id),
    ...{ class: "id-value" },
}));
const __VLS_23 = __VLS_22({
    id: (__VLS_ctx.data.id),
    ...{ class: "id-value" },
}, ...__VLS_functionalComponentArgsRest(__VLS_22));
/** @type {__VLS_StyleScopedClasses['id-value']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "description" },
});
/** @type {__VLS_StyleScopedClasses['description']} */ ;
if (__VLS_ctx.data.description) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text" },
    });
    /** @type {__VLS_StyleScopedClasses['text']} */ ;
    (__VLS_ctx.data.description);
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text" },
});
/** @type {__VLS_StyleScopedClasses['text']} */ ;
(__VLS_ctx.updatedText);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "capabilities" },
});
/** @type {__VLS_StyleScopedClasses['capabilities']} */ ;
if (__VLS_ctx.data.capabilities.deploy) {
    let __VLS_26;
    /** @ts-ignore @type { | typeof __VLS_components.Rocket | typeof __VLS_components.Rocket} */
    Rocket;
    // @ts-ignore
    const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
        size: (16),
    }));
    const __VLS_28 = __VLS_27({
        size: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_27));
    __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, value: ('Deploy') }, null, null);
}
if (__VLS_ctx.data.slug) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "slug" },
    });
    /** @type {__VLS_StyleScopedClasses['slug']} */ ;
    (__VLS_ctx.data.slug);
}
const __VLS_31 = SatellitesEditModal || SatellitesEditModal;
// @ts-ignore
const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
    visible: (__VLS_ctx.showEditModal),
    data: (__VLS_ctx.data),
}));
const __VLS_33 = __VLS_32({
    visible: (__VLS_ctx.showEditModal),
    data: (__VLS_ctx.data),
}, ...__VLS_functionalComponentArgsRest(__VLS_32));
const __VLS_36 = SatellitesApiKeyModal || SatellitesApiKeyModal;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent1(__VLS_36, new __VLS_36({
    visible: (__VLS_ctx.showApiKey),
    apiKey: (null),
    satelliteId: (__VLS_ctx.data.id),
}));
const __VLS_38 = __VLS_37({
    visible: (__VLS_ctx.showApiKey),
    apiKey: (null),
    satelliteId: (__VLS_ctx.data.id),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
// @ts-ignore
var __VLS_20 = __VLS_19;
// @ts-ignore
[vTooltip, data, data, data, data, data, data, data, data, menuItems, updatedText, showEditModal, showApiKey,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
