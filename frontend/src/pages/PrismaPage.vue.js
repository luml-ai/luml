/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, computed, provide, watch, onMounted } from 'vue';
import { useRoute, useRouter, RouterView } from 'vue-router';
import { Tabs, TabList, Tab, TabPanels, TabPanel, Button, Dialog, Tag } from 'primevue';
import { KanbanSquare, FolderGit, Plus, Monitor, Terminal } from 'lucide-vue-next';
import { api } from '@/lib/api';
import { usePrismaStore } from '@/stores/prisma';
import { useBackendStatus } from '@/hooks/useBackendStatus';
import BackendOffline from '@/components/prisma/BackendOffline.vue';
import BackendIndicator from '@/components/prisma/BackendIndicator.vue';
import NewRepositoryDialog from '@/components/prisma/NewRepositoryDialog.vue';
import NewItemDialog from '@/components/prisma/NewItemDialog.vue';
import TerminalPanel from '@/components/prisma/TerminalPanel.vue';
import BoardView from '@/pages/prisma/BoardView.vue';
import RepositoriesView from '@/pages/prisma/RepositoriesView.vue';
const store = usePrismaStore();
const route = useRoute();
const router = useRouter();
const { isOffline, isLoading, versionMismatch, check } = useBackendStatus();
const repositories = ref([]);
const showNewRepository = ref(false);
const newItemType = ref(null);
const showDebugSessions = ref(false);
const debugSessions = ref([]);
const terminalSessionId = ref(null);
const terminalLabel = ref('Terminal');
const showTerminal = ref(false);
const isDetailRoute = computed(() => route.name === 'prisma-task' || route.name === 'prisma-run');
const activeTab = ref(route.name === 'prisma-repos' ? 'repositories' : 'board');
watch(() => route.name, (name) => {
    if (name === 'prisma-board')
        activeTab.value = 'board';
    else if (name === 'prisma-repos')
        activeTab.value = 'repositories';
});
watch(activeTab, (tab) => {
    const target = tab === 'repositories' ? 'prisma-repos' : 'prisma-board';
    if (route.name !== target) {
        router.replace({ name: target });
    }
});
const tabsListPT = {
    tabList: { style: 'border-left: none; border-top: none; border-right: none;' },
};
const boardRefreshTrigger = ref(0);
provide('showNewRepository', showNewRepository);
provide('newItemType', newItemType);
provide('boardRefreshTrigger', boardRefreshTrigger);
async function refreshRepositories() {
    repositories.value = await api.dataAgent.listRepositories();
    store.repositories = repositories.value;
}
async function openDebugSessions() {
    debugSessions.value = await api.dataAgent.getDebugSessions();
    showDebugSessions.value = true;
}
function openTerminalDialog(sessionId, label) {
    terminalSessionId.value = sessionId;
    terminalLabel.value = label ?? 'Terminal';
    showTerminal.value = true;
}
function closeTerminal() {
    showTerminal.value = false;
    terminalSessionId.value = null;
}
function openDebugTerminal(sessionId) {
    openTerminalDialog(sessionId, 'Debug session');
    showDebugSessions.value = false;
}
function onRepositoryCreated() {
    showNewRepository.value = false;
    refreshRepositories();
}
function onItemCreated() {
    newItemType.value = null;
    boardRefreshTrigger.value++;
}
async function onRetry() {
    const ok = await check();
    if (ok)
        refreshRepositories();
}
async function onBackendChanged() {
    const ok = await check();
    if (ok)
        refreshRepositories();
}
onMounted(async () => {
    const ok = await check();
    if (ok)
        refreshRepositories();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['prisma-page']} */ ;
/** @type {__VLS_StyleScopedClasses['prisma-page']} */ ;
/** @type {__VLS_StyleScopedClasses['prisma-page']} */ ;
/** @type {__VLS_StyleScopedClasses['prisma-page']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "prisma-page" },
    ...{ class: ({ 'is-detail': __VLS_ctx.isDetailRoute }) },
});
/** @type {__VLS_StyleScopedClasses['prisma-page']} */ ;
/** @type {__VLS_StyleScopedClasses['is-detail']} */ ;
if (__VLS_ctx.isLoading) {
}
else if (__VLS_ctx.isOffline || __VLS_ctx.versionMismatch) {
    const __VLS_0 = BackendOffline;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onRetry': {} },
        versionMismatch: (__VLS_ctx.versionMismatch),
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onRetry': {} },
        versionMismatch: (__VLS_ctx.versionMismatch),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ retry: {} },
        { onRetry: (__VLS_ctx.onRetry) });
    var __VLS_3;
    var __VLS_4;
}
else {
    if (!__VLS_ctx.isDetailRoute) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
            ...{ class: "page-header" },
        });
        /** @type {__VLS_StyleScopedClasses['page-header']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "title-row" },
        });
        /** @type {__VLS_StyleScopedClasses['title-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
            ...{ class: "title" },
        });
        /** @type {__VLS_StyleScopedClasses['title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "preview-badge" },
        });
        __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { bottom: true, }, value: ('This feature is in preview and may change as we refine it.') }, null, null);
        /** @type {__VLS_StyleScopedClasses['preview-badge']} */ ;
        const __VLS_7 = BackendIndicator;
        // @ts-ignore
        const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
            ...{ 'onChanged': {} },
        }));
        const __VLS_9 = __VLS_8({
            ...{ 'onChanged': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_8));
        let __VLS_12;
        const __VLS_13 = ({ changed: {} },
            { onChanged: (__VLS_ctx.onBackendChanged) });
        var __VLS_10;
        var __VLS_11;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "header-actions" },
        });
        /** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
        let __VLS_14;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
            ...{ 'onClick': {} },
            severity: "secondary",
            outlined: true,
        }));
        const __VLS_16 = __VLS_15({
            ...{ 'onClick': {} },
            severity: "secondary",
            outlined: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_15));
        let __VLS_19;
        const __VLS_20 = ({ click: {} },
            { onClick: (__VLS_ctx.openDebugSessions) });
        const { default: __VLS_21 } = __VLS_17.slots;
        let __VLS_22;
        /** @ts-ignore @type { | typeof __VLS_components.Monitor} */
        Monitor;
        // @ts-ignore
        const __VLS_23 = __VLS_asFunctionalComponent1(__VLS_22, new __VLS_22({
            size: (14),
        }));
        const __VLS_24 = __VLS_23({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_23));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        // @ts-ignore
        [isDetailRoute, isDetailRoute, isLoading, isOffline, versionMismatch, versionMismatch, onRetry, vTooltip, onBackendChanged, openDebugSessions,];
        var __VLS_17;
        var __VLS_18;
        let __VLS_27;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_28 = __VLS_asFunctionalComponent1(__VLS_27, new __VLS_27({
            ...{ 'onClick': {} },
        }));
        const __VLS_29 = __VLS_28({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_28));
        let __VLS_32;
        const __VLS_33 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.isLoading))
                        return;
                    if (!!(__VLS_ctx.isOffline || __VLS_ctx.versionMismatch))
                        return;
                    if (!(!__VLS_ctx.isDetailRoute))
                        return;
                    __VLS_ctx.showNewRepository = true;
                    // @ts-ignore
                    [showNewRepository,];
                } });
        const { default: __VLS_34 } = __VLS_30.slots;
        let __VLS_35;
        /** @ts-ignore @type { | typeof __VLS_components.Plus} */
        Plus;
        // @ts-ignore
        const __VLS_36 = __VLS_asFunctionalComponent1(__VLS_35, new __VLS_35({
            size: (14),
        }));
        const __VLS_37 = __VLS_36({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_36));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        // @ts-ignore
        [];
        var __VLS_30;
        var __VLS_31;
    }
    if (__VLS_ctx.isDetailRoute) {
        let __VLS_40;
        /** @ts-ignore @type { | typeof __VLS_components.RouterView} */
        RouterView;
        // @ts-ignore
        const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({}));
        const __VLS_42 = __VLS_41({}, ...__VLS_functionalComponentArgsRest(__VLS_41));
    }
    else {
        let __VLS_45;
        /** @ts-ignore @type { | typeof __VLS_components.Tabs | typeof __VLS_components.Tabs} */
        Tabs;
        // @ts-ignore
        const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({
            value: (__VLS_ctx.activeTab),
            ...{ class: "main-tabs" },
        }));
        const __VLS_47 = __VLS_46({
            value: (__VLS_ctx.activeTab),
            ...{ class: "main-tabs" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_46));
        /** @type {__VLS_StyleScopedClasses['main-tabs']} */ ;
        const { default: __VLS_50 } = __VLS_48.slots;
        let __VLS_51;
        /** @ts-ignore @type { | typeof __VLS_components.TabList | typeof __VLS_components.TabList} */
        TabList;
        // @ts-ignore
        const __VLS_52 = __VLS_asFunctionalComponent1(__VLS_51, new __VLS_51({
            pt: (__VLS_ctx.tabsListPT),
        }));
        const __VLS_53 = __VLS_52({
            pt: (__VLS_ctx.tabsListPT),
        }, ...__VLS_functionalComponentArgsRest(__VLS_52));
        const { default: __VLS_56 } = __VLS_54.slots;
        let __VLS_57;
        /** @ts-ignore @type { | typeof __VLS_components.Tab | typeof __VLS_components.Tab} */
        Tab;
        // @ts-ignore
        const __VLS_58 = __VLS_asFunctionalComponent1(__VLS_57, new __VLS_57({
            value: "board",
            ...{ class: "tab" },
        }));
        const __VLS_59 = __VLS_58({
            value: "board",
            ...{ class: "tab" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_58));
        /** @type {__VLS_StyleScopedClasses['tab']} */ ;
        const { default: __VLS_62 } = __VLS_60.slots;
        let __VLS_63;
        /** @ts-ignore @type { | typeof __VLS_components.KanbanSquare} */
        KanbanSquare;
        // @ts-ignore
        const __VLS_64 = __VLS_asFunctionalComponent1(__VLS_63, new __VLS_63({
            size: (14),
        }));
        const __VLS_65 = __VLS_64({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_64));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        // @ts-ignore
        [isDetailRoute, activeTab, tabsListPT,];
        var __VLS_60;
        let __VLS_68;
        /** @ts-ignore @type { | typeof __VLS_components.Tab | typeof __VLS_components.Tab} */
        Tab;
        // @ts-ignore
        const __VLS_69 = __VLS_asFunctionalComponent1(__VLS_68, new __VLS_68({
            value: "repositories",
            ...{ class: "tab" },
        }));
        const __VLS_70 = __VLS_69({
            value: "repositories",
            ...{ class: "tab" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_69));
        /** @type {__VLS_StyleScopedClasses['tab']} */ ;
        const { default: __VLS_73 } = __VLS_71.slots;
        let __VLS_74;
        /** @ts-ignore @type { | typeof __VLS_components.FolderGit} */
        FolderGit;
        // @ts-ignore
        const __VLS_75 = __VLS_asFunctionalComponent1(__VLS_74, new __VLS_74({
            size: (14),
        }));
        const __VLS_76 = __VLS_75({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_75));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        // @ts-ignore
        [];
        var __VLS_71;
        // @ts-ignore
        [];
        var __VLS_54;
        let __VLS_79;
        /** @ts-ignore @type { | typeof __VLS_components.TabPanels | typeof __VLS_components.TabPanels} */
        TabPanels;
        // @ts-ignore
        const __VLS_80 = __VLS_asFunctionalComponent1(__VLS_79, new __VLS_79({
            ...{ class: "panels" },
        }));
        const __VLS_81 = __VLS_80({
            ...{ class: "panels" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_80));
        /** @type {__VLS_StyleScopedClasses['panels']} */ ;
        const { default: __VLS_84 } = __VLS_82.slots;
        let __VLS_85;
        /** @ts-ignore @type { | typeof __VLS_components.TabPanel | typeof __VLS_components.TabPanel} */
        TabPanel;
        // @ts-ignore
        const __VLS_86 = __VLS_asFunctionalComponent1(__VLS_85, new __VLS_85({
            value: "board",
            ...{ class: "panel" },
        }));
        const __VLS_87 = __VLS_86({
            value: "board",
            ...{ class: "panel" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_86));
        /** @type {__VLS_StyleScopedClasses['panel']} */ ;
        const { default: __VLS_90 } = __VLS_88.slots;
        const __VLS_91 = BoardView;
        // @ts-ignore
        const __VLS_92 = __VLS_asFunctionalComponent1(__VLS_91, new __VLS_91({}));
        const __VLS_93 = __VLS_92({}, ...__VLS_functionalComponentArgsRest(__VLS_92));
        // @ts-ignore
        [];
        var __VLS_88;
        let __VLS_96;
        /** @ts-ignore @type { | typeof __VLS_components.TabPanel | typeof __VLS_components.TabPanel} */
        TabPanel;
        // @ts-ignore
        const __VLS_97 = __VLS_asFunctionalComponent1(__VLS_96, new __VLS_96({
            value: "repositories",
            ...{ class: "panel" },
        }));
        const __VLS_98 = __VLS_97({
            value: "repositories",
            ...{ class: "panel" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_97));
        /** @type {__VLS_StyleScopedClasses['panel']} */ ;
        const { default: __VLS_101 } = __VLS_99.slots;
        const __VLS_102 = RepositoriesView;
        // @ts-ignore
        const __VLS_103 = __VLS_asFunctionalComponent1(__VLS_102, new __VLS_102({}));
        const __VLS_104 = __VLS_103({}, ...__VLS_functionalComponentArgsRest(__VLS_103));
        // @ts-ignore
        [];
        var __VLS_99;
        // @ts-ignore
        [];
        var __VLS_82;
        // @ts-ignore
        [];
        var __VLS_48;
    }
}
const __VLS_107 = NewRepositoryDialog;
// @ts-ignore
const __VLS_108 = __VLS_asFunctionalComponent1(__VLS_107, new __VLS_107({
    ...{ 'onClose': {} },
    ...{ 'onCreated': {} },
    visible: (__VLS_ctx.showNewRepository),
}));
const __VLS_109 = __VLS_108({
    ...{ 'onClose': {} },
    ...{ 'onCreated': {} },
    visible: (__VLS_ctx.showNewRepository),
}, ...__VLS_functionalComponentArgsRest(__VLS_108));
let __VLS_112;
const __VLS_113 = ({ close: {} },
    { onClose: (...[$event]) => {
            __VLS_ctx.showNewRepository = false;
            // @ts-ignore
            [showNewRepository, showNewRepository,];
        } });
const __VLS_114 = ({ created: {} },
    { onCreated: (__VLS_ctx.onRepositoryCreated) });
var __VLS_110;
var __VLS_111;
const __VLS_115 = NewItemDialog;
// @ts-ignore
const __VLS_116 = __VLS_asFunctionalComponent1(__VLS_115, new __VLS_115({
    ...{ 'onClose': {} },
    ...{ 'onCreated': {} },
    visible: (__VLS_ctx.newItemType !== null),
    initialType: (__VLS_ctx.newItemType ?? 'workflow'),
    repositories: (__VLS_ctx.repositories),
}));
const __VLS_117 = __VLS_116({
    ...{ 'onClose': {} },
    ...{ 'onCreated': {} },
    visible: (__VLS_ctx.newItemType !== null),
    initialType: (__VLS_ctx.newItemType ?? 'workflow'),
    repositories: (__VLS_ctx.repositories),
}, ...__VLS_functionalComponentArgsRest(__VLS_116));
let __VLS_120;
const __VLS_121 = ({ close: {} },
    { onClose: (...[$event]) => {
            __VLS_ctx.newItemType = null;
            // @ts-ignore
            [onRepositoryCreated, newItemType, newItemType, newItemType, repositories,];
        } });
const __VLS_122 = ({ created: {} },
    { onCreated: (__VLS_ctx.onItemCreated) });
var __VLS_118;
var __VLS_119;
let __VLS_123;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_124 = __VLS_asFunctionalComponent1(__VLS_123, new __VLS_123({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.showDebugSessions),
    header: "PTY Sessions",
    modal: true,
    ...{ style: ({ width: '600px' }) },
}));
const __VLS_125 = __VLS_124({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.showDebugSessions),
    header: "PTY Sessions",
    modal: true,
    ...{ style: ({ width: '600px' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_124));
let __VLS_128;
const __VLS_129 = ({ 'update:visible': {} },
    { 'onUpdate:visible': (...[$event]) => {
            !$event && (__VLS_ctx.showDebugSessions = false);
            // @ts-ignore
            [onItemCreated, showDebugSessions, showDebugSessions,];
        } });
const { default: __VLS_130 } = __VLS_126.slots;
if (__VLS_ctx.debugSessions.length === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sessions-empty" },
    });
    /** @type {__VLS_StyleScopedClasses['sessions-empty']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sessions-list" },
    });
    /** @type {__VLS_StyleScopedClasses['sessions-list']} */ ;
    for (const [s] of __VLS_vFor((__VLS_ctx.debugSessions))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (s.session_id),
            ...{ class: "session-card" },
        });
        /** @type {__VLS_StyleScopedClasses['session-card']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "session-header" },
        });
        /** @type {__VLS_StyleScopedClasses['session-header']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.code, __VLS_intrinsics.code)({
            ...{ class: "session-id" },
        });
        /** @type {__VLS_StyleScopedClasses['session-id']} */ ;
        (s.session_id.substring(0, 12));
        let __VLS_131;
        /** @ts-ignore @type { | typeof __VLS_components.Tag} */
        Tag;
        // @ts-ignore
        const __VLS_132 = __VLS_asFunctionalComponent1(__VLS_131, new __VLS_131({
            value: (s.alive ? 'alive' : 'dead'),
            severity: (s.alive ? 'success' : 'danger'),
        }));
        const __VLS_133 = __VLS_132({
            value: (s.alive ? 'alive' : 'dead'),
            severity: (s.alive ? 'success' : 'danger'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_132));
        let __VLS_136;
        /** @ts-ignore @type { | typeof __VLS_components.Tag} */
        Tag;
        // @ts-ignore
        const __VLS_137 = __VLS_asFunctionalComponent1(__VLS_136, new __VLS_136({
            value: (s.session_type),
            severity: "info",
        }));
        const __VLS_138 = __VLS_137({
            value: (s.session_type),
            severity: "info",
        }, ...__VLS_functionalComponentArgsRest(__VLS_137));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "session-details" },
        });
        /** @type {__VLS_StyleScopedClasses['session-details']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (s.pid);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (s.task_id);
        if (s.exit_code != null) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (s.exit_code);
        }
        if (s.alive) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "session-actions" },
            });
            /** @type {__VLS_StyleScopedClasses['session-actions']} */ ;
            let __VLS_141;
            /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
            Button;
            // @ts-ignore
            const __VLS_142 = __VLS_asFunctionalComponent1(__VLS_141, new __VLS_141({
                ...{ 'onClick': {} },
                size: "small",
            }));
            const __VLS_143 = __VLS_142({
                ...{ 'onClick': {} },
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_142));
            let __VLS_146;
            const __VLS_147 = ({ click: {} },
                { onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.debugSessions.length === 0))
                            return;
                        if (!(s.alive))
                            return;
                        __VLS_ctx.openDebugTerminal(s.session_id);
                        // @ts-ignore
                        [debugSessions, debugSessions, openDebugTerminal,];
                    } });
            const { default: __VLS_148 } = __VLS_144.slots;
            let __VLS_149;
            /** @ts-ignore @type { | typeof __VLS_components.Terminal} */
            Terminal;
            // @ts-ignore
            const __VLS_150 = __VLS_asFunctionalComponent1(__VLS_149, new __VLS_149({
                size: (14),
            }));
            const __VLS_151 = __VLS_150({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_150));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            // @ts-ignore
            [];
            var __VLS_144;
            var __VLS_145;
        }
        // @ts-ignore
        [];
    }
}
// @ts-ignore
[];
var __VLS_126;
var __VLS_127;
let __VLS_154;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_155 = __VLS_asFunctionalComponent1(__VLS_154, new __VLS_154({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.showTerminal),
    header: (__VLS_ctx.terminalLabel),
    draggable: (true),
    modal: (false),
    ...{ style: ({ width: '960px', height: '580px' }) },
    contentStyle: ({
        padding: 0,
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        overflow: 'hidden',
    }),
    ...{ class: "terminal-dialog" },
    position: "bottom",
}));
const __VLS_156 = __VLS_155({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.showTerminal),
    header: (__VLS_ctx.terminalLabel),
    draggable: (true),
    modal: (false),
    ...{ style: ({ width: '960px', height: '580px' }) },
    contentStyle: ({
        padding: 0,
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        overflow: 'hidden',
    }),
    ...{ class: "terminal-dialog" },
    position: "bottom",
}, ...__VLS_functionalComponentArgsRest(__VLS_155));
let __VLS_159;
const __VLS_160 = ({ 'update:visible': {} },
    { 'onUpdate:visible': (...[$event]) => {
            !$event && __VLS_ctx.closeTerminal();
            // @ts-ignore
            [showTerminal, terminalLabel, closeTerminal,];
        } });
/** @type {__VLS_StyleScopedClasses['terminal-dialog']} */ ;
const { default: __VLS_161 } = __VLS_157.slots;
if (__VLS_ctx.terminalSessionId) {
    const __VLS_162 = TerminalPanel;
    // @ts-ignore
    const __VLS_163 = __VLS_asFunctionalComponent1(__VLS_162, new __VLS_162({
        sessionId: (__VLS_ctx.terminalSessionId),
        active: (__VLS_ctx.showTerminal),
        taskName: (__VLS_ctx.terminalLabel),
    }));
    const __VLS_164 = __VLS_163({
        sessionId: (__VLS_ctx.terminalSessionId),
        active: (__VLS_ctx.showTerminal),
        taskName: (__VLS_ctx.terminalLabel),
    }, ...__VLS_functionalComponentArgsRest(__VLS_163));
}
// @ts-ignore
[showTerminal, terminalLabel, terminalSessionId, terminalSessionId,];
var __VLS_157;
var __VLS_158;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
