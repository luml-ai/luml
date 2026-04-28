import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  AgentRepository,
  AgentTask,
  Run,
  RunNode,
  RunEdge,
  RunEvent,
  RunGraph,
} from '@/lib/api/prisma/prisma.interfaces'

export const usePrismaStore = defineStore('prisma', () => {
  const repositories = ref<AgentRepository[]>([])
  const tasks = ref<AgentTask[]>([])

  const selectedTaskId = ref<string | null>(null)

  const selectedTask = computed(
    () => tasks.value.find((t) => t.id === selectedTaskId.value) ?? null,
  )

  const runs = ref<Run[]>([])
  const selectedRunId = ref<string | null>(null)
  const nodes = ref<RunNode[]>([])
  const edges = ref<RunEdge[]>([])
  const selectedNodeId = ref<string | null>(null)
  const lastSeq = ref(0)

  const selectedRun = computed(() => runs.value.find((r) => r.id === selectedRunId.value) ?? null)

  const selectedNode = computed(
    () => nodes.value.find((n) => n.id === selectedNodeId.value) ?? null,
  )

  function setRuns(newRuns: Run[]) {
    runs.value = newRuns
  }

  function selectRun(id: string | null) {
    selectedRunId.value = id
    if (id === null) {
      nodes.value = []
      edges.value = []
      selectedNodeId.value = null
      lastSeq.value = 0
    }
  }

  function selectNode(id: string | null) {
    selectedNodeId.value = id
  }

  function applySnapshot(graph: RunGraph & { run?: Run }) {
    nodes.value = graph.nodes
    edges.value = graph.edges
    if (graph.run) {
      const idx = runs.value.findIndex((r) => r.id === graph.run!.id)
      if (idx >= 0) {
        runs.value[idx] = graph.run
      }
    }
  }

  function applyEvent(event: RunEvent) {
    if (event.seq > lastSeq.value) {
      lastSeq.value = event.seq
    }

    switch (event.type) {
      case 'node_created': {
        const data = event.data
        if (data.node_id && !nodes.value.find((n) => n.id === data.node_id)) {
          nodes.value.push({
            id: data.node_id,
            run_id: selectedRunId.value ?? '',
            parent_node_id: data.parent_node_id ?? null,
            node_type: data.node_type ?? '',
            status: 'queued',
            depth: data.depth ?? 0,
            payload: {},
            result: {},
            worktree_path: '',
            branch: '',
            debug_retries: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          })
        }
        break
      }
      case 'node_status_changed': {
        const node = nodes.value.find((n) => n.id === event.node_id)
        if (node && event.data.status) {
          node.status = event.data.status
        }
        break
      }
      case 'node_session_started': {
        const node = nodes.value.find((n) => n.id === event.node_id)
        if (node && event.data.session_id) {
          node.session_id = event.data.session_id
          node.is_alive = true
        }
        break
      }
      case 'node_completed': {
        const node = nodes.value.find((n) => n.id === event.node_id)
        if (node) {
          node.status = event.data.status ?? node.status
          if (event.data.result) {
            node.result = event.data.result
          }
          node.is_alive = false
        }
        break
      }
      case 'edge_created': {
        const data = event.data
        if (data.from_node_id && data.to_node_id) {
          edges.value.push({
            id: `e${data.from_node_id}-${data.to_node_id}`,
            run_id: selectedRunId.value ?? '',
            from_node_id: data.from_node_id,
            to_node_id: data.to_node_id,
            reason: data.reason ?? 'auto',
          })
        }
        break
      }
      case 'node_updated': {
        const node = nodes.value.find((n) => n.id === event.node_id)
        if (node && event.data.result) {
          node.result = event.data.result
        }
        break
      }
      case 'run_status_changed': {
        const run = runs.value.find((r) => r.id === selectedRunId.value)
        if (run && event.data.status) {
          run.status = event.data.status
        }
        if (run && event.data.best_node_id !== undefined) {
          run.best_node_id = event.data.best_node_id
        }
        break
      }
    }
  }

  function updateRun(run: Run) {
    const idx = runs.value.findIndex((r) => r.id === run.id)
    if (idx >= 0) {
      runs.value[idx] = run
    } else {
      runs.value.unshift(run)
    }
  }

  function removeRun(id: string) {
    runs.value = runs.value.filter((r) => r.id !== id)
    if (selectedRunId.value === id) {
      selectRun(null)
    }
  }

  function selectTask(id: string | null) {
    selectedTaskId.value = id
  }

  function updateTask(task: AgentTask) {
    const idx = tasks.value.findIndex((t) => t.id === task.id)
    if (idx >= 0) {
      tasks.value[idx] = task
    } else {
      tasks.value.unshift(task)
    }
  }

  function removeTask(id: string) {
    tasks.value = tasks.value.filter((t) => t.id !== id)
    if (selectedTaskId.value === id) {
      selectTask(null)
    }
  }

  return {
    repositories,
    tasks,
    selectedTaskId,
    selectedTask,
    runs,
    selectedRunId,
    selectedRun,
    nodes,
    edges,
    selectedNodeId,
    selectedNode,
    lastSeq,
    setRuns,
    selectRun,
    selectNode,
    selectTask,
    updateTask,
    removeTask,
    applySnapshot,
    applyEvent,
    updateRun,
    removeRun,
  }
})
