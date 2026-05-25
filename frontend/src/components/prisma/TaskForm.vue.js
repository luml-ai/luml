/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, watch, onMounted } from 'vue';
import { InputText, Textarea, Select, Checkbox } from 'primevue';
import { api } from '@/lib/api';
const __VLS_props = defineProps();
const emit = defineEmits();
const name = ref('');
const selectedRepository = ref(null);
const selectedAgent = ref(null);
const prompt = ref('');
const agents = ref([]);
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
let branchAbort = null;
onMounted(async () => {
    agents.value = await api.dataAgent.listAvailableAgents();
    if (agents.value.length > 0) {
        selectedAgent.value = agents.value[0];
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
    if (!selectedRepository.value || !selectedAgent.value)
        return;
    emit('submit', {
        repository_id: selectedRepository.value.id,
        name: name.value,
        agent_id: selectedAgent.value.id,
        prompt: prompt.value,
        base_branch: baseBranch.value,
    });
    name.value = '';
    prompt.value = '';
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
        inputId: "showAgentBranchesTask",
    }));
    const __VLS_12 = __VLS_11({
        modelValue: (__VLS_ctx.showAgentBranches),
        binary: (true),
        inputId: "showAgentBranchesTask",
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: "showAgentBranchesTask",
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
/** @ts-ignore @type { | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    modelValue: (__VLS_ctx.selectedAgent),
    options: (__VLS_ctx.agents),
    optionLabel: "name",
    placeholder: "Select an agent",
    ...{ class: "w-full" },
}));
const __VLS_17 = __VLS_16({
    modelValue: (__VLS_ctx.selectedAgent),
    options: (__VLS_ctx.agents),
    optionLabel: "name",
    placeholder: "Select an agent",
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
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    modelValue: (__VLS_ctx.name),
    placeholder: "fix-auth-bug",
    ...{ class: "w-full" },
}));
const __VLS_22 = __VLS_21({
    modelValue: (__VLS_ctx.name),
    placeholder: "fix-auth-bug",
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
/** @ts-ignore @type { | typeof __VLS_components.Textarea} */
Textarea;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
    modelValue: (__VLS_ctx.prompt),
    rows: "4",
    placeholder: "Describe what the agent should do...",
    ...{ class: "w-full" },
}));
const __VLS_27 = __VLS_26({
    modelValue: (__VLS_ctx.prompt),
    rows: "4",
    placeholder: "Describe what the agent should do...",
    ...{ class: "w-full" },
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
// @ts-ignore
[selectedRepository, selectedRepository, repositories, baseBranch, filteredBranches, branchesLoading, branchesLoading, hasAgentBranches, showAgentBranches, selectedAgent, agents, name, prompt,];
const __VLS_export = (await import('vue')).defineComponent({
    setup: () => __VLS_exposed,
    __typeEmits: {},
    __typeProps: {},
});
export default {};
