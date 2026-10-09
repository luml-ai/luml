import { LINEAGE_FLOW_ID } from '@/components/lineage/lineage.data'
import type {
  HistorySnapshot,
  LineageCanvasNode,
  LineageNodeData,
} from '@/components/lineage/lineage.interface'
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import { api } from '@/lib/api'
import { useArtifactsStore } from '@/stores/artifacts'
import {
  useVueFlow,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type XYPosition,
} from '@vue-flow/core'
import { defineStore } from 'pinia'
import { computed, nextTick, onScopeDispose, ref, shallowRef } from 'vue'
import { useRoute } from 'vue-router'
import { buildLineageBatch, isEmptyLineageBatch } from './diff'
import { freePositionNear, layoutLineageNodes } from './layout'
import {
  artifactCanvasNodeId,
  artifactNodeData,
  mapGraphToCanvas,
  type LineageFocalArtifact,
} from './mapping'
import { countUnconnectedArtifacts, isValidLineageConnection } from './validation'

const STATE_CHANGE_DEBOUNCE_MS = 200

function cloneState(state: HistorySnapshot): HistorySnapshot {
  return JSON.parse(JSON.stringify(state)) as HistorySnapshot
}

export const useLineageStore = defineStore('lineage', () => {
  // The id ties the store to the canvas: without it Vue Flow would hand every
  // new mount of the canvas its own instance and the store's edits would never
  // reach it (see LINEAGE_FLOW_ID).
  const { nodes, edges, addEdges, onConnect, onNodesChange, onEdgesChange, setNodes, setEdges } =
    useVueFlow(LINEAGE_FLOW_ID)
  const route = useRoute()
  const artifactsStore = useArtifactsStore()

  const currentArtifactId = computed(() => String(route.params.artifactId))
  const creatorVisible = ref(false)
  const detailedArtifact = ref<LineageNodeData | null>(null)
  const initialNodes = shallowRef<LineageCanvasNode[]>([])
  const initialEdges = shallowRef<Edge[]>([])
  const loadedState = shallowRef<HistorySnapshot>({ nodes: [], edges: [] })
  const replaceableArtifactId = ref<string | null>(null)
  const history = shallowRef<HistorySnapshot[]>([])
  const truncated = ref(false)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const loadFailed = ref(false)
  // The artifact whose graph the canvas shows; null until a load succeeds.
  const loadedArtifactId = ref<string | null>(null)

  let stableState: HistorySnapshot = { nodes: [], edges: [] }
  let historyWindowOpen = false
  let historyTimer: ReturnType<typeof setTimeout> | null = null
  let isRestoring = false
  let latestLoad = 0

  function snapshot(): HistorySnapshot {
    return cloneState({
      nodes: nodes.value as unknown as LineageCanvasNode[],
      edges: edges.value,
    })
  }

  function closeHistoryWindow(): void {
    if (historyTimer) clearTimeout(historyTimer)
    historyTimer = null
    if (!historyWindowOpen) return
    stableState = snapshot()
    historyWindowOpen = false
  }

  function recordFlowChange(): void {
    if (isRestoring) return
    if (!historyWindowOpen) {
      history.value = [...history.value, cloneState(stableState)]
      historyWindowOpen = true
    }
    if (historyTimer) clearTimeout(historyTimer)
    historyTimer = setTimeout(closeHistoryWindow, STATE_CHANGE_DEBOUNCE_MS)
  }

  function replaceCanvasWithEdit(state: HistorySnapshot): void {
    closeHistoryWindow()
    const previous = snapshot()
    const nextState = cloneState(state)
    isRestoring = true
    setNodes(nextState.nodes)
    setEdges(nextState.edges)
    history.value = [...history.value, previous]
    stableState = snapshot()
    isRestoring = false
  }

  function replaceCanvasWithoutHistory(state: HistorySnapshot): void {
    closeHistoryWindow()
    const nextState = cloneState(state)
    isRestoring = true
    setNodes(nextState.nodes)
    setEdges(nextState.edges)
    initialNodes.value = cloneState(nextState).nodes
    initialEdges.value = cloneState(nextState).edges
    loadedState.value = cloneState(nextState)
    history.value = []
    stableState = snapshot()
    isRestoring = false
  }

  function currentFocalArtifact(): LineageFocalArtifact {
    const artifact = artifactsStore.currentArtifact
    if (!artifact) throw new Error('Current artifact does not exist')

    const detailed = artifact as Artifact & {
      collection?: { id: string; name: string }
    }
    return {
      ...artifact,
      collection: detailed.collection ?? {
        id: artifact.collection_id,
        name: artifact.collection_name,
      },
    }
  }

  function requestInfo(): { organizationId: string; orbitId: string; artifactId: string } {
    if (typeof route.params.organizationId !== 'string') {
      throw new Error('Current organization not found')
    }
    if (typeof route.params.id !== 'string') throw new Error('Orbit was not found')
    if (typeof route.params.artifactId !== 'string') throw new Error('Artifact was not found')
    return {
      organizationId: route.params.organizationId,
      orbitId: route.params.id,
      artifactId: route.params.artifactId,
    }
  }

  // The tab always shows the whole graph around the artifact; the platform
  // only cuts it at its node cap.
  async function load(): Promise<void> {
    const loadId = ++latestLoad
    const { organizationId, orbitId, artifactId } = requestInfo()
    const focalArtifact = currentFocalArtifact()
    if (loadedArtifactId.value !== artifactId) {
      // Another artifact's graph must not stay on the canvas under this
      // route: saving it would edit that artifact's lineage.
      loadedArtifactId.value = null
      replaceCanvasWithoutHistory({ nodes: [], edges: [] })
      truncated.value = false
    }
    loadFailed.value = false
    isLoading.value = true
    try {
      const graph = await api.lineage.getGraph(organizationId, orbitId, artifactId)
      if (loadId !== latestLoad) return
      replaceCanvasWithoutHistory(mapGraphToCanvas(graph, focalArtifact))
      truncated.value = graph.truncated
      loadedArtifactId.value = artifactId
    } catch (error) {
      if (loadId === latestLoad) {
        // Whatever is on the canvas is not a graph that can be saved.
        loadedArtifactId.value = null
        loadFailed.value = true
      }
      throw error
    } finally {
      if (loadId === latestLoad) isLoading.value = false
    }
  }

  // Edits are possible only on the graph of the artifact this route shows,
  // and never while a request is replacing it.
  const isEditable = computed(
    () =>
      !isLoading.value &&
      !isSaving.value &&
      loadedArtifactId.value !== null &&
      loadedArtifactId.value === currentArtifactId.value,
  )

  // Unlink and replace act on every connection of a node. A truncated graph
  // hides some of them, so the node, or the replaced artifact, would come
  // back with its hidden connections after a reload.
  const canRewire = computed(() => isEditable.value && !truncated.value)

  function goBack(): void {
    if (!isEditable.value) return
    closeHistoryWindow()
    const state = history.value[history.value.length - 1]
    if (!state) return

    history.value = history.value.slice(0, -1)
    isRestoring = true
    const previous = cloneState(state)
    setNodes(previous.nodes)
    setEdges(previous.edges)
    stableState = snapshot()
    void nextTick(() => {
      isRestoring = false
    })
  }

  const usedArtifactsIds = computed(() => {
    const ids = (nodes.value as unknown as LineageCanvasNode[])
      .map((node) => node.data.artifactId)
      .filter((id): id is string => id !== null)
    return [...new Set(ids)]
  })

  const unconnectedArtifactsCount = computed(() =>
    countUnconnectedArtifacts(nodes.value as unknown as LineageCanvasNode[], edges.value),
  )

  // Undoable steps that would reach the server: moving the focal node of an
  // empty graph is undoable but has nothing to save.
  const hasEdits = computed(() => {
    if (history.value.length === 0) return false
    try {
      return !isEmptyLineageBatch(
        buildLineageBatch(loadedState.value, {
          nodes: nodes.value as unknown as LineageCanvasNode[],
          edges: edges.value,
        }),
      )
    } catch {
      // A canvas mid-update can hold an edge whose node is not there yet.
      return true
    }
  })
  const hasNodes = computed(() => nodes.value.length > 0)
  const hasEdges = computed(() => edges.value.length > 0)

  function setCreatorVisible(value: boolean): void {
    creatorVisible.value = value
  }

  function setDetailedArtifact(artifact: LineageNodeData | null): void {
    detailedArtifact.value = artifact
  }

  function addArtifact(artifact: Artifact, position?: XYPosition): void {
    if (!isEditable.value || usedArtifactsIds.value.includes(artifact.id)) return
    const state = snapshot()
    const anchor = state.nodes.find((node) => node.data.variant === 'main') ?? state.nodes[0]
    state.nodes.push({
      id: artifactCanvasNodeId(artifact.id),
      type: 'lineage',
      position:
        position ??
        freePositionNear(
          anchor?.position ?? { x: 0, y: 0 },
          state.nodes.map((node) => node.position),
        ),
      data: artifactNodeData(artifact, {
        id: artifact.collection_id,
        name: artifact.collection_name,
      }),
    })
    replaceCanvasWithEdit(state)
  }

  function replaceArtifact(artifact: Artifact): void {
    const oldId = replaceableArtifactId.value
    if (!canRewire.value || !oldId || usedArtifactsIds.value.includes(artifact.id)) return
    const state = snapshot()
    const nodeToReplace = state.nodes.find((node) => node.id === oldId)
    if (!nodeToReplace || nodeToReplace.data.variant === 'main') return

    const newId = artifactCanvasNodeId(artifact.id)
    state.nodes = state.nodes.map((node) =>
      node.id === oldId
        ? {
            ...node,
            id: newId,
            connectable: true,
            data: artifactNodeData(artifact, {
              id: artifact.collection_id,
              name: artifact.collection_name,
            }),
          }
        : node,
    )
    state.edges = state.edges.map((edge) => ({
      ...edge,
      source: edge.source === oldId ? newId : edge.source,
      target: edge.target === oldId ? newId : edge.target,
    }))
    replaceCanvasWithEdit(state)
  }

  function unlinkArtifact(artifactId: string): void {
    if (!canRewire.value) return
    const state = snapshot()
    const node = state.nodes.find((candidate) => candidate.id === artifactId)
    if (!node || node.data.variant === 'main') return
    replaceCanvasWithEdit({
      nodes: state.nodes.filter((candidate) => candidate.id !== artifactId),
      edges: state.edges.filter((edge) => edge.source !== artifactId && edge.target !== artifactId),
    })
  }

  function setReplaceableArtifactId(artifactId: string | null): void {
    replaceableArtifactId.value = artifactId
  }

  function resetPositions(): void {
    if (!isEditable.value) return
    const state = snapshot()
    if (state.nodes.length === 0) return
    const focalNode = state.nodes.find((node) => node.data.variant === 'main') ?? state.nodes[0]
    replaceCanvasWithEdit({
      nodes: layoutLineageNodes(state.nodes, state.edges, focalNode.id),
      edges: state.edges,
    })
  }

  function discardChanges(): void {
    if (isSaving.value) return
    replaceCanvasWithoutHistory(loadedState.value)
    detailedArtifact.value = null
  }

  async function save(): Promise<void> {
    // A second save while one is in flight would resend the same batch.
    if (isSaving.value) return
    closeHistoryWindow()
    if (!hasEdits.value || unconnectedArtifactsCount.value > 0) return

    const { organizationId, orbitId, artifactId } = requestInfo()
    if (!isEditable.value || loadedArtifactId.value !== artifactId) {
      throw new Error('The lineage on the canvas belongs to another artifact. Refresh the page.')
    }
    // The canvas is locked (isEditable) until the request settles, so the
    // batch cannot miss an edit made in the meantime.
    isSaving.value = true
    try {
      const changes = buildLineageBatch(loadedState.value, snapshot())
      await api.lineage.applyChanges(organizationId, orbitId, changes)
      // The server now holds what the canvas shows: forget the edits before
      // the reload so a failed reload cannot lead to the same batch being
      // sent twice.
      replaceCanvasWithoutHistory(snapshot())
    } finally {
      isSaving.value = false
    }
    try {
      await load()
    } catch {
      throw new Error('Changes were saved, but the graph could not be reloaded. Refresh the page.')
    }
  }

  // A deleted artifact's node exists only for its connections: once the last
  // one is removed it would only block saving, and the server drops it anyway.
  function pruneEdgelessDeletedNodes(): void {
    if (isRestoring) return
    const current = nodes.value as unknown as LineageCanvasNode[]
    const connected = new Set(edges.value.flatMap((edge) => [edge.source, edge.target]))
    const kept = current.filter((node) => !node.data.isDeleted || connected.has(node.id))
    if (kept.length === current.length) return
    setNodes(kept as unknown as Node[])
    recordFlowChange()
  }

  onConnect((connection) => {
    if (
      !isEditable.value ||
      !isValidLineageConnection(
        connection,
        nodes.value as unknown as LineageCanvasNode[],
        edges.value,
      )
    ) {
      return
    }
    addEdges({ ...connection, type: 'custom' })
  })

  onNodesChange((changes: NodeChange[]) => {
    if (changes.some((change) => ['add', 'remove', 'position'].includes(change.type))) {
      recordFlowChange()
    }
  })

  onEdgesChange((changes: EdgeChange[]) => {
    if (changes.some((change) => change.type === 'add' || change.type === 'remove')) {
      recordFlowChange()
    }
    if (changes.some((change) => change.type === 'remove')) {
      void nextTick(pruneEdgelessDeletedNodes)
    }
  })

  onScopeDispose(() => {
    if (historyTimer) clearTimeout(historyTimer)
  })

  return {
    creatorVisible,
    setCreatorVisible,
    detailedArtifact,
    setDetailedArtifact,
    addArtifact,
    initialNodes,
    initialEdges,
    unlinkArtifact,
    usedArtifactsIds,
    replaceableArtifactId,
    setReplaceableArtifactId,
    replaceArtifact,
    history,
    hasEdits,
    hasNodes,
    hasEdges,
    unconnectedArtifactsCount,
    truncated,
    isLoading,
    isSaving,
    isEditable,
    canRewire,
    loadFailed,
    loadedArtifactId,
    currentArtifactId,
    load,
    goBack,
    discardChanges,
    resetPositions,
    save,
  }
})
