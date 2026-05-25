/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { reactive, ref, watch } from 'vue';
import { Tabs, TabList, Tab, TabPanels, TabPanel } from 'primevue';
import TerminalPanel from './TerminalPanel.vue';
const props = defineProps();
const emit = defineEmits();
const activeTab = ref('');
const idleSessions = reactive(new Set());
function onIdleChange(sessionId, idle) {
    if (idle) {
        idleSessions.add(sessionId);
    }
    else {
        idleSessions.delete(sessionId);
    }
    emit('update:idleSessions', [...idleSessions]);
}
watch(() => props.tasks, (tasks) => {
    if (tasks.length > 0 && !tasks.some((t) => t.session_id === activeTab.value)) {
        activeTab.value = tasks[0].session_id ?? '';
    }
}, { immediate: true });
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
/** @type {__VLS_StyleScopedClasses['terminal-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['terminal-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['terminal-tabs']} */ ;
if (__VLS_ctx.tasks.length > 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "terminal-tabs" },
    });
    /** @type {__VLS_StyleScopedClasses['terminal-tabs']} */ ;
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.Tabs | typeof __VLS_components.Tabs} */
    Tabs;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        value: (__VLS_ctx.activeTab),
    }));
    const __VLS_2 = __VLS_1({
        value: (__VLS_ctx.activeTab),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    const { default: __VLS_5 } = __VLS_3.slots;
    let __VLS_6;
    /** @ts-ignore @type { | typeof __VLS_components.TabList | typeof __VLS_components.TabList} */
    TabList;
    // @ts-ignore
    const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({}));
    const __VLS_8 = __VLS_7({}, ...__VLS_functionalComponentArgsRest(__VLS_7));
    const { default: __VLS_11 } = __VLS_9.slots;
    for (const [task] of __VLS_vFor((__VLS_ctx.tasks))) {
        let __VLS_12;
        /** @ts-ignore @type { | typeof __VLS_components.Tab | typeof __VLS_components.Tab} */
        Tab;
        // @ts-ignore
        const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
            key: (task.session_id),
            value: (task.session_id ?? ''),
        }));
        const __VLS_14 = __VLS_13({
            key: (task.session_id),
            value: (task.session_id ?? ''),
        }, ...__VLS_functionalComponentArgsRest(__VLS_13));
        const { default: __VLS_17 } = __VLS_15.slots;
        (task.name);
        // @ts-ignore
        [tasks, tasks, activeTab,];
        var __VLS_15;
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_9;
    let __VLS_18;
    /** @ts-ignore @type { | typeof __VLS_components.TabPanels | typeof __VLS_components.TabPanels} */
    TabPanels;
    // @ts-ignore
    const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({}));
    const __VLS_20 = __VLS_19({}, ...__VLS_functionalComponentArgsRest(__VLS_19));
    const { default: __VLS_23 } = __VLS_21.slots;
    for (const [task] of __VLS_vFor((__VLS_ctx.tasks))) {
        let __VLS_24;
        /** @ts-ignore @type { | typeof __VLS_components.TabPanel | typeof __VLS_components.TabPanel} */
        TabPanel;
        // @ts-ignore
        const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
            key: (task.session_id),
            value: (task.session_id ?? ''),
        }));
        const __VLS_26 = __VLS_25({
            key: (task.session_id),
            value: (task.session_id ?? ''),
        }, ...__VLS_functionalComponentArgsRest(__VLS_25));
        const { default: __VLS_29 } = __VLS_27.slots;
        if (task.session_id) {
            const __VLS_30 = TerminalPanel;
            // @ts-ignore
            const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
                ...{ 'onIdleChange': {} },
                sessionId: (task.session_id),
                active: (__VLS_ctx.activeTab === task.session_id),
                taskName: (task.name),
            }));
            const __VLS_32 = __VLS_31({
                ...{ 'onIdleChange': {} },
                sessionId: (task.session_id),
                active: (__VLS_ctx.activeTab === task.session_id),
                taskName: (task.name),
            }, ...__VLS_functionalComponentArgsRest(__VLS_31));
            let __VLS_35;
            const __VLS_36 = ({ idleChange: {} },
                { onIdleChange: ((idle) => __VLS_ctx.onIdleChange(task.session_id, idle)) });
            var __VLS_33;
            var __VLS_34;
        }
        // @ts-ignore
        [tasks, activeTab, onIdleChange,];
        var __VLS_27;
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_21;
    // @ts-ignore
    [];
    var __VLS_3;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "no-terminals" },
    });
    /** @type {__VLS_StyleScopedClasses['no-terminals']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({});
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
