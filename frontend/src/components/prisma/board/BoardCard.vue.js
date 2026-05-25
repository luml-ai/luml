/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed } from 'vue';
import { Tag, Button } from 'primevue';
import { Waypoints, ListTodo, Play, Trash2 } from 'lucide-vue-next';
import { statusSeverity } from './board.types';
const props = defineProps();
const emit = defineEmits();
const name = computed(() => props.item.data.name);
const isTask = computed(() => props.item.kind === 'task');
const waitingInput = computed(() => !!props.item.data.has_waiting_input);
const displayStatus = computed(() => waitingInput.value ? 'waiting for input' : props.item.data.status);
const severityValue = computed(() => waitingInput.value ? 'warn' : statusSeverity(props.item.data.status));
const relativeTime = computed(() => {
    const ms = Date.now() - new Date(props.item.data.updated_at).getTime();
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60)
        return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60)
        return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24)
        return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
});
const showStart = computed(() => props.item.data.status === 'pending');
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
/** @type {__VLS_StyleScopedClasses['board-card']} */ ;
/** @type {__VLS_StyleScopedClasses['board-card']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-actions']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.emit('select');
            // @ts-ignore
            [emit,];
        } },
    ...{ class: "board-card" },
});
/** @type {__VLS_StyleScopedClasses['board-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card-top" },
});
/** @type {__VLS_StyleScopedClasses['card-top']} */ ;
const __VLS_0 = (__VLS_ctx.isTask ? __VLS_ctx.ListTodo : __VLS_ctx.Waypoints);
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    size: (14),
    ...{ class: "type-icon" },
}));
const __VLS_2 = __VLS_1({
    size: (14),
    ...{ class: "type-icon" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['type-icon']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "card-name" },
});
/** @type {__VLS_StyleScopedClasses['card-name']} */ ;
(__VLS_ctx.name);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card-meta" },
});
/** @type {__VLS_StyleScopedClasses['card-meta']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "repo-name" },
});
/** @type {__VLS_StyleScopedClasses['repo-name']} */ ;
(__VLS_ctx.repositoryName);
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.Tag} */
Tag;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    value: (__VLS_ctx.displayStatus),
    severity: (__VLS_ctx.severityValue),
    ...{ class: "status-tag" },
}));
const __VLS_7 = __VLS_6({
    value: (__VLS_ctx.displayStatus),
    severity: (__VLS_ctx.severityValue),
    ...{ class: "status-tag" },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
/** @type {__VLS_StyleScopedClasses['status-tag']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card-footer" },
});
/** @type {__VLS_StyleScopedClasses['card-footer']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "time" },
});
/** @type {__VLS_StyleScopedClasses['time']} */ ;
(__VLS_ctx.relativeTime);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ onClick: () => { } },
    ...{ class: "quick-actions" },
});
/** @type {__VLS_StyleScopedClasses['quick-actions']} */ ;
if (__VLS_ctx.showStart) {
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "success",
        ...{ class: "action-btn" },
    }));
    const __VLS_12 = __VLS_11({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "success",
        ...{ class: "action-btn" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    let __VLS_15;
    const __VLS_16 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.showStart))
                    return;
                __VLS_ctx.emit('start');
                // @ts-ignore
                [emit, isTask, ListTodo, Waypoints, name, repositoryName, displayStatus, severityValue, relativeTime, showStart,];
            } });
    __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { top: true, }, value: ('Start') }, null, null);
    /** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
    const { default: __VLS_17 } = __VLS_13.slots;
    {
        const { icon: __VLS_18 } = __VLS_13.slots;
        let __VLS_19;
        /** @ts-ignore @type { | typeof __VLS_components.Play} */
        Play;
        // @ts-ignore
        const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
            size: (14),
        }));
        const __VLS_21 = __VLS_20({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_20));
        // @ts-ignore
        [vTooltip,];
    }
    // @ts-ignore
    [];
    var __VLS_13;
    var __VLS_14;
}
let __VLS_24;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
    ...{ class: "action-btn" },
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
    ...{ class: "action-btn" },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_29;
const __VLS_30 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.emit('delete');
            // @ts-ignore
            [emit,];
        } });
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { top: true, }, value: ('Delete') }, null, null);
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
const { default: __VLS_31 } = __VLS_27.slots;
{
    const { icon: __VLS_32 } = __VLS_27.slots;
    let __VLS_33;
    /** @ts-ignore @type { | typeof __VLS_components.Trash2} */
    Trash2;
    // @ts-ignore
    const __VLS_34 = __VLS_asFunctionalComponent1(__VLS_33, new __VLS_33({
        size: (14),
    }));
    const __VLS_35 = __VLS_34({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_34));
    // @ts-ignore
    [vTooltip,];
}
// @ts-ignore
[];
var __VLS_27;
var __VLS_28;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
