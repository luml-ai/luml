export interface WorkflowFormData {
    repository_id: string;
    name: string;
    objective: string;
    base_branch: string;
    agent_id: string | undefined;
    run_command: string | undefined;
    max_depth: number;
    max_children_per_fork: number;
    max_debug_retries: number;
    max_concurrency: number;
    auto_mode: boolean;
    auto_terminate_timeout: number;
    implement_timeout: number;
    run_timeout: number;
    debug_timeout: number;
    fork_timeout: number;
    luml_collection_id: string | undefined;
    luml_organization_id: string | undefined;
    luml_orbit_id: string | undefined;
}
declare const __VLS_export: any;
declare const _default: typeof __VLS_export;
export default _default;
