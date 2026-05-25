/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, watch, onMounted, computed } from 'vue';
import { InputText, InputNumber, Textarea, Select, Checkbox } from 'primevue';
import { ChevronDown, ChevronUp } from 'lucide-vue-next';
import { api } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
const __VLS_props = defineProps();
const emit = defineEmits();
const name = ref('');
const selectedRepository = ref(null);
const selectedAgent = ref(null);
const objective = ref('');
const baseBranch = ref('main');
const branchOptions = ref([]);
const branchesLoading = ref(false);
const showAgentBranches = ref(false);
const AGENT_PREFIXES = ['prisma/'];
function isAgentBranch(branch) {
    return AGENT_PREFIXES.some((p) => branch.startsWith(p));
}
function filteredBranches() {
    if (showAgentBranches.value)
        return branchOptions.value;
    return branchOptions.value.filter((b) => !isAgentBranch(b));
}
function hasAgentBranches() {
    return branchOptions.value.some((b) => isAgentBranch(b));
}
const runCommand = ref('uv run main.py');
const maxDepth = ref(2);
const maxChildrenPerFork = ref(2);
const maxDebugRetries = ref(2);
const maxConcurrency = ref(1);
const autoMode = ref(false);
const autoTerminateTimeout = ref(30);
const implementTimeout = ref(3600);
const runTimeout = ref(0);
const debugTimeout = ref(1800);
const forkTimeout = ref(1200);
const agents = ref([]);
const showAdvanced = ref(false);
const authStore = useAuthStore();
const orgStore = useOrganizationStore();
const orbits = ref([]);
const selectedOrbit = ref(null);
const orbitsLoading = ref(false);
const collections = ref([]);
const selectedCollection = ref(null);
const collectionsLoading = ref(false);
const uploadEnabled = ref(false);
const showCollectionSelector = computed(() => authStore.isAuth && orgStore.currentOrganization);
let branchAbort = null;
async function loadOrbits() {
    const orgId = orgStore.currentOrganization?.id;
    if (!orgId)
        return;
    orbitsLoading.value = true;
    try {
        orbits.value = await api.getOrganizationOrbits(orgId);
    }
    catch {
        orbits.value = [];
    }
    finally {
        orbitsLoading.value = false;
    }
}
async function loadCollections() {
    const orgId = orgStore.currentOrganization?.id;
    const orbitId = selectedOrbit.value?.id;
    if (!orgId || !orbitId)
        return;
    collectionsLoading.value = true;
    try {
        const resp = await api.orbitCollections.getCollectionsList(orgId, orbitId, {
            cursor: null,
            limit: 100,
        });
        collections.value = resp.items;
    }
    catch {
        collections.value = [];
    }
    finally {
        collectionsLoading.value = false;
    }
}
onMounted(async () => {
    agents.value = await api.dataAgent.listAvailableAgents();
    if (agents.value.length > 0) {
        selectedAgent.value = agents.value[0];
    }
});
watch(uploadEnabled, (enabled) => {
    if (!enabled) {
        selectedOrbit.value = null;
        selectedCollection.value = null;
    }
    else if (orbits.value.length === 0) {
        loadOrbits();
    }
});
watch(selectedOrbit, (orbit) => {
    selectedCollection.value = null;
    collections.value = [];
    if (orbit) {
        loadCollections();
    }
});
watch(selectedRepository, async (repo) => {
    branchAbort?.abort();
    branchOptions.value = [];
    showAgentBranches.value = false;
    if (!repo)
        return;
    branchAbort = new AbortController();
    branchesLoading.value = true;
    try {
        const branches = await api.dataAgent.listBranches(repo.path, { signal: branchAbort.signal });
        branchOptions.value = branches;
        if (branches.length > 0) {
            baseBranch.value = branches.includes('main') ? 'main' : branches[0];
        }
    }
    catch {
        // ignore aborted or failed fetches
    }
    finally {
        branchesLoading.value = false;
    }
});
function submit() {
    if (!selectedRepository.value)
        return;
    const col = selectedCollection.value;
    emit('submit', {
        repository_id: selectedRepository.value.id,
        name: name.value,
        objective: objective.value,
        base_branch: baseBranch.value,
        agent_id: selectedAgent.value?.id,
        run_command: runCommand.value || undefined,
        max_depth: maxDepth.value,
        max_children_per_fork: maxChildrenPerFork.value,
        max_debug_retries: maxDebugRetries.value,
        max_concurrency: maxConcurrency.value,
        auto_mode: autoMode.value,
        auto_terminate_timeout: autoTerminateTimeout.value,
        implement_timeout: implementTimeout.value,
        run_timeout: runTimeout.value,
        debug_timeout: debugTimeout.value,
        fork_timeout: forkTimeout.value,
        luml_collection_id: col?.id,
        luml_organization_id: col ? orgStore.currentOrganization?.id : undefined,
        luml_orbit_id: col ? selectedOrbit.value?.id : undefined,
    });
    name.value = '';
    objective.value = '';
    runCommand.value = 'uv run main.py';
    uploadEnabled.value = false;
    selectedOrbit.value = null;
    selectedCollection.value = null;
}
const __VLS_exposed = { submit };
defineExpose(__VLS_exposed);
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
/** @type {__VLS_StyleScopedClasses['advanced-toggle']} */ ;
/** @type {__VLS_StyleScopedClasses['field--small']} */ ;
/** @type {__VLS_StyleScopedClasses['field--small']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form" },
});
/** @type {__VLS_StyleScopedClasses['form']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.selectedRepository),
    options: (__VLS_ctx.repositories),
    optionLabel: "name",
    placeholder: "Select a repository",
    ...{ class: "w-full" },
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.selectedRepository),
    options: (__VLS_ctx.repositories),
    optionLabel: "name",
    placeholder: "Select a repository",
    ...{ class: "w-full" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    modelValue: (__VLS_ctx.baseBranch),
    options: (__VLS_ctx.filteredBranches()),
    disabled: (!__VLS_ctx.selectedRepository),
    loading: (__VLS_ctx.branchesLoading),
    editable: true,
    placeholder: (__VLS_ctx.branchesLoading ? 'Loading branches…' : 'Select a repository first'),
    ...{ class: "w-full" },
}));
const __VLS_7 = __VLS_6({
    modelValue: (__VLS_ctx.baseBranch),
    options: (__VLS_ctx.filteredBranches()),
    disabled: (!__VLS_ctx.selectedRepository),
    loading: (__VLS_ctx.branchesLoading),
    editable: true,
    placeholder: (__VLS_ctx.branchesLoading ? 'Loading branches…' : 'Select a repository first'),
    ...{ class: "w-full" },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
if (__VLS_ctx.hasAgentBranches()) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "agent-branch-toggle" },
    });
    /** @type {__VLS_StyleScopedClasses['agent-branch-toggle']} */ ;
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.Checkbox} */
    Checkbox;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        modelValue: (__VLS_ctx.showAgentBranches),
        binary: (true),
        inputId: "showAgentBranchesWorkflow",
    }));
    const __VLS_12 = __VLS_11({
        modelValue: (__VLS_ctx.showAgentBranches),
        binary: (true),
        inputId: "showAgentBranchesWorkflow",
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: "showAgentBranchesWorkflow",
    });
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_15;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    modelValue: (__VLS_ctx.name),
    placeholder: "my-feature-workflow",
    ...{ class: "w-full" },
}));
const __VLS_17 = __VLS_16({
    modelValue: (__VLS_ctx.name),
    placeholder: "my-feature-workflow",
    ...{ class: "w-full" },
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.Textarea} */
Textarea;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    modelValue: (__VLS_ctx.objective),
    rows: "3",
    placeholder: "Describe what this workflow should accomplish...",
    ...{ class: "w-full" },
}));
const __VLS_22 = __VLS_21({
    modelValue: (__VLS_ctx.objective),
    rows: "3",
    placeholder: "Describe what this workflow should accomplish...",
    ...{ class: "w-full" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_25;
/** @ts-ignore @type { | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
    modelValue: (__VLS_ctx.selectedAgent),
    options: (__VLS_ctx.agents),
    optionLabel: "name",
    placeholder: "Select an agent",
    ...{ class: "w-full" },
}));
const __VLS_27 = __VLS_26({
    modelValue: (__VLS_ctx.selectedAgent),
    options: (__VLS_ctx.agents),
    optionLabel: "name",
    placeholder: "Select an agent",
    ...{ class: "w-full" },
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field field--checkbox" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
/** @type {__VLS_StyleScopedClasses['field--checkbox']} */ ;
let __VLS_30;
/** @ts-ignore @type { | typeof __VLS_components.Checkbox} */
Checkbox;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
    modelValue: (__VLS_ctx.autoMode),
    binary: (true),
    inputId: "autoMode",
}));
const __VLS_32 = __VLS_31({
    modelValue: (__VLS_ctx.autoMode),
    binary: (true),
    inputId: "autoMode",
}, ...__VLS_functionalComponentArgsRest(__VLS_31));
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "autoMode",
});
if (__VLS_ctx.autoMode) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field field--small" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    /** @type {__VLS_StyleScopedClasses['field--small']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_35;
    /** @ts-ignore @type { | typeof __VLS_components.InputNumber} */
    InputNumber;
    // @ts-ignore
    const __VLS_36 = __VLS_asFunctionalComponent1(__VLS_35, new __VLS_35({
        modelValue: (__VLS_ctx.autoTerminateTimeout),
        min: (5),
        max: (300),
    }));
    const __VLS_37 = __VLS_36({
        modelValue: (__VLS_ctx.autoTerminateTimeout),
        min: (5),
        max: (300),
    }, ...__VLS_functionalComponentArgsRest(__VLS_36));
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "option-group" },
});
/** @type {__VLS_StyleScopedClasses['option-group']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field field--checkbox" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
/** @type {__VLS_StyleScopedClasses['field--checkbox']} */ ;
let __VLS_40;
/** @ts-ignore @type { | typeof __VLS_components.Checkbox} */
Checkbox;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
    modelValue: (__VLS_ctx.uploadEnabled),
    binary: (true),
    inputId: "uploadEnabled",
    disabled: (!__VLS_ctx.showCollectionSelector),
}));
const __VLS_42 = __VLS_41({
    modelValue: (__VLS_ctx.uploadEnabled),
    binary: (true),
    inputId: "uploadEnabled",
    disabled: (!__VLS_ctx.showCollectionSelector),
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "uploadEnabled",
    ...{ class: ({ 'label--disabled': !__VLS_ctx.showCollectionSelector }) },
});
/** @type {__VLS_StyleScopedClasses['label--disabled']} */ ;
if (!__VLS_ctx.showCollectionSelector) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "hint" },
    });
    /** @type {__VLS_StyleScopedClasses['hint']} */ ;
}
if (__VLS_ctx.uploadEnabled && __VLS_ctx.showCollectionSelector) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_45;
    /** @ts-ignore @type { | typeof __VLS_components.Select} */
    Select;
    // @ts-ignore
    const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({
        modelValue: (__VLS_ctx.selectedOrbit),
        options: (__VLS_ctx.orbits),
        optionLabel: "name",
        loading: (__VLS_ctx.orbitsLoading),
        placeholder: "Select an orbit",
        showClear: true,
        ...{ class: "w-full" },
    }));
    const __VLS_47 = __VLS_46({
        modelValue: (__VLS_ctx.selectedOrbit),
        options: (__VLS_ctx.orbits),
        optionLabel: "name",
        loading: (__VLS_ctx.orbitsLoading),
        placeholder: "Select an orbit",
        showClear: true,
        ...{ class: "w-full" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_46));
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    if (__VLS_ctx.selectedOrbit) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "field" },
        });
        /** @type {__VLS_StyleScopedClasses['field']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            ...{ class: "label" },
        });
        /** @type {__VLS_StyleScopedClasses['label']} */ ;
        let __VLS_50;
        /** @ts-ignore @type { | typeof __VLS_components.Select} */
        Select;
        // @ts-ignore
        const __VLS_51 = __VLS_asFunctionalComponent1(__VLS_50, new __VLS_50({
            modelValue: (__VLS_ctx.selectedCollection),
            options: (__VLS_ctx.collections),
            optionLabel: "name",
            loading: (__VLS_ctx.collectionsLoading),
            placeholder: "Select a collection",
            showClear: true,
            ...{ class: "w-full" },
        }));
        const __VLS_52 = __VLS_51({
            modelValue: (__VLS_ctx.selectedCollection),
            options: (__VLS_ctx.collections),
            optionLabel: "name",
            loading: (__VLS_ctx.collectionsLoading),
            placeholder: "Select a collection",
            showClear: true,
            ...{ class: "w-full" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_51));
        /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.showAdvanced = !__VLS_ctx.showAdvanced;
            // @ts-ignore
            [selectedRepository, selectedRepository, repositories, baseBranch, filteredBranches, branchesLoading, branchesLoading, hasAgentBranches, showAgentBranches, name, objective, selectedAgent, agents, autoMode, autoMode, autoTerminateTimeout, uploadEnabled, uploadEnabled, showCollectionSelector, showCollectionSelector, showCollectionSelector, showCollectionSelector, selectedOrbit, selectedOrbit, orbits, orbitsLoading, selectedCollection, collections, collectionsLoading, showAdvanced, showAdvanced,];
        } },
    type: "button",
    ...{ class: "advanced-toggle" },
});
/** @type {__VLS_StyleScopedClasses['advanced-toggle']} */ ;
const __VLS_55 = (__VLS_ctx.showAdvanced ? __VLS_ctx.ChevronUp : __VLS_ctx.ChevronDown);
// @ts-ignore
const __VLS_56 = __VLS_asFunctionalComponent1(__VLS_55, new __VLS_55({
    size: (14),
}));
const __VLS_57 = __VLS_56({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_56));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
if (__VLS_ctx.showAdvanced) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_60;
    /** @ts-ignore @type { | typeof __VLS_components.InputText} */
    InputText;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent1(__VLS_60, new __VLS_60({
        modelValue: (__VLS_ctx.runCommand),
        placeholder: "uv run main.py",
        ...{ class: "w-full" },
    }));
    const __VLS_62 = __VLS_61({
        modelValue: (__VLS_ctx.runCommand),
        placeholder: "uv run main.py",
        ...{ class: "w-full" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "config-row" },
    });
    /** @type {__VLS_StyleScopedClasses['config-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field field--small" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    /** @type {__VLS_StyleScopedClasses['field--small']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_65;
    /** @ts-ignore @type { | typeof __VLS_components.InputNumber} */
    InputNumber;
    // @ts-ignore
    const __VLS_66 = __VLS_asFunctionalComponent1(__VLS_65, new __VLS_65({
        modelValue: (__VLS_ctx.maxDepth),
        min: (1),
        max: (10),
    }));
    const __VLS_67 = __VLS_66({
        modelValue: (__VLS_ctx.maxDepth),
        min: (1),
        max: (10),
    }, ...__VLS_functionalComponentArgsRest(__VLS_66));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field field--small" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    /** @type {__VLS_StyleScopedClasses['field--small']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_70;
    /** @ts-ignore @type { | typeof __VLS_components.InputNumber} */
    InputNumber;
    // @ts-ignore
    const __VLS_71 = __VLS_asFunctionalComponent1(__VLS_70, new __VLS_70({
        modelValue: (__VLS_ctx.maxChildrenPerFork),
        min: (1),
        max: (10),
    }));
    const __VLS_72 = __VLS_71({
        modelValue: (__VLS_ctx.maxChildrenPerFork),
        min: (1),
        max: (10),
    }, ...__VLS_functionalComponentArgsRest(__VLS_71));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "config-row" },
    });
    /** @type {__VLS_StyleScopedClasses['config-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field field--small" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    /** @type {__VLS_StyleScopedClasses['field--small']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_75;
    /** @ts-ignore @type { | typeof __VLS_components.InputNumber} */
    InputNumber;
    // @ts-ignore
    const __VLS_76 = __VLS_asFunctionalComponent1(__VLS_75, new __VLS_75({
        modelValue: (__VLS_ctx.maxDebugRetries),
        min: (0),
        max: (10),
    }));
    const __VLS_77 = __VLS_76({
        modelValue: (__VLS_ctx.maxDebugRetries),
        min: (0),
        max: (10),
    }, ...__VLS_functionalComponentArgsRest(__VLS_76));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field field--small" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    /** @type {__VLS_StyleScopedClasses['field--small']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_80;
    /** @ts-ignore @type { | typeof __VLS_components.InputNumber} */
    InputNumber;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent1(__VLS_80, new __VLS_80({
        modelValue: (__VLS_ctx.maxConcurrency),
        min: (1),
        max: (10),
    }));
    const __VLS_82 = __VLS_81({
        modelValue: (__VLS_ctx.maxConcurrency),
        min: (1),
        max: (10),
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "config-row" },
    });
    /** @type {__VLS_StyleScopedClasses['config-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field field--small" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    /** @type {__VLS_StyleScopedClasses['field--small']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_85;
    /** @ts-ignore @type { | typeof __VLS_components.InputNumber} */
    InputNumber;
    // @ts-ignore
    const __VLS_86 = __VLS_asFunctionalComponent1(__VLS_85, new __VLS_85({
        modelValue: (__VLS_ctx.implementTimeout),
        min: (0),
        max: (7200),
    }));
    const __VLS_87 = __VLS_86({
        modelValue: (__VLS_ctx.implementTimeout),
        min: (0),
        max: (7200),
    }, ...__VLS_functionalComponentArgsRest(__VLS_86));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field field--small" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    /** @type {__VLS_StyleScopedClasses['field--small']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_90;
    /** @ts-ignore @type { | typeof __VLS_components.InputNumber} */
    InputNumber;
    // @ts-ignore
    const __VLS_91 = __VLS_asFunctionalComponent1(__VLS_90, new __VLS_90({
        modelValue: (__VLS_ctx.runTimeout),
        min: (0),
        max: (86400),
    }));
    const __VLS_92 = __VLS_91({
        modelValue: (__VLS_ctx.runTimeout),
        min: (0),
        max: (86400),
    }, ...__VLS_functionalComponentArgsRest(__VLS_91));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "config-row" },
    });
    /** @type {__VLS_StyleScopedClasses['config-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field field--small" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    /** @type {__VLS_StyleScopedClasses['field--small']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_95;
    /** @ts-ignore @type { | typeof __VLS_components.InputNumber} */
    InputNumber;
    // @ts-ignore
    const __VLS_96 = __VLS_asFunctionalComponent1(__VLS_95, new __VLS_95({
        modelValue: (__VLS_ctx.debugTimeout),
        min: (0),
        max: (7200),
    }));
    const __VLS_97 = __VLS_96({
        modelValue: (__VLS_ctx.debugTimeout),
        min: (0),
        max: (7200),
    }, ...__VLS_functionalComponentArgsRest(__VLS_96));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "field field--small" },
    });
    /** @type {__VLS_StyleScopedClasses['field']} */ ;
    /** @type {__VLS_StyleScopedClasses['field--small']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    let __VLS_100;
    /** @ts-ignore @type { | typeof __VLS_components.InputNumber} */
    InputNumber;
    // @ts-ignore
    const __VLS_101 = __VLS_asFunctionalComponent1(__VLS_100, new __VLS_100({
        modelValue: (__VLS_ctx.forkTimeout),
        min: (0),
        max: (7200),
    }));
    const __VLS_102 = __VLS_101({
        modelValue: (__VLS_ctx.forkTimeout),
        min: (0),
        max: (7200),
    }, ...__VLS_functionalComponentArgsRest(__VLS_101));
}
// @ts-ignore
[showAdvanced, showAdvanced, ChevronUp, ChevronDown, runCommand, maxDepth, maxChildrenPerFork, maxDebugRetries, maxConcurrency, implementTimeout, runTimeout, debugTimeout, forkTimeout,];
const __VLS_export = (await import('vue')).defineComponent({
    setup: () => __VLS_exposed,
    __typeEmits: {},
    __typeProps: {},
});
export default {};
