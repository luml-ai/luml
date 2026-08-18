import type { HistorySnapshot, LineageNodeData } from '@/components/lineage/lineage.interface'
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import { useVueFlow, type Edge, type Node } from '@vue-flow/core'
import { useDebounceFn } from '@vueuse/core'
import { defineStore } from 'pinia'
import { computed, nextTick, ref, shallowRef } from 'vue'
import { useRoute } from 'vue-router'

export const useLineageStore = defineStore('lineage', () => {
  const {
    nodes,
    edges,
    addNodes,
    removeNodes,
    onConnect,
    addEdges,
    onNodesChange,
    onEdgesChange,
    setNodes,
    setEdges,
  } = useVueFlow()
  const route = useRoute()

  const currentArtifactId = computed(() => String(route.params.artifactId))

  const creatorVisible = ref(false)
  const detailedArtifact = ref<Artifact | null>(null)
  const initialNodes = shallowRef<Node[]>([])
  const initialEdges = shallowRef<Edge[]>([])
  const replaceableArtifactId = ref<string | null>(null)

  const history = shallowRef<HistorySnapshot[]>([])
  let isRestoring = false

  const snapshot = () => ({
    nodes: JSON.parse(JSON.stringify(nodes.value)),
    edges: JSON.parse(JSON.stringify(edges.value)),
  })

  let prev: HistorySnapshot = snapshot()

  function goBack() {
    const state = history.value[history.value.length - 1]
    history.value = history.value.slice(0, -1)
    if (!state) return
    isRestoring = true
    setNodes(state.nodes)
    setEdges(state.edges)
    nextTick(() => {
      prev = snapshot()
      isRestoring = false
    })
  }

  const usedArtifactsIds = computed(() => {
    return nodes.value.map((node) => node.id)
  })

  function setCreatorVisible(value: boolean) {
    creatorVisible.value = value
  }

  function setDetailedArtifact(artifact: Artifact | null) {
    detailedArtifact.value = artifact
  }

  function addArtifact(artifact: Artifact) {
    const node: Node = {
      id: artifact.id,
      type: 'lineage',
      position: { x: 20, y: 20 },
      data: prepareNodeData(artifact),
    }
    addNodes(node)
  }

  function replaceArtifact(artifact: Artifact) {
    if (!replaceableArtifactId.value) return
    const nodeToReplace = nodes.value.find((node) => node.id === replaceableArtifactId.value)
    if (!nodeToReplace) return
    removeNodes([nodeToReplace])
    addNodes({
      ...nodeToReplace,
      id: artifact.id,
      data: prepareNodeData(artifact),
    })
  }

  function prepareNodeData(artifact: Artifact): LineageNodeData {
    const variant = artifact.id === currentArtifactId.value ? 'main' : 'default'
    return {
      type: artifact.type,
      title: artifact.name,
      collectionName: artifact.collection_name,
      variant,
      deployments: artifact.deployments,
      tracks: artifact.tracks,
    }
  }

  function unlinkArtifact(artifactId: string) {
    const node = nodes.value.find((node) => node.id === artifactId)
    if (!node) return
    removeNodes([node])
  }

  function setReplaceableArtifactId(artifactId: string | null) {
    replaceableArtifactId.value = artifactId
  }

  function onStateChanged() {
    if (isRestoring) return
    history.value = [...history.value, prev]
    prev = snapshot()
  }

  function resetPositions() {
    if (history.value.length === 0 || isRestoring) return
    isRestoring = true
    setNodes(history.value[0].nodes)
    setEdges(history.value[0].edges)
    history.value = []
    nextTick(() => {
      isRestoring = false
    })
  }

  async function save() {
    await new Promise((resolve) => setTimeout(resolve, 1000))
    // await api.lineage.save(history.value)
    isRestoring = true
    initialNodes.value = nodes.value
    initialEdges.value = edges.value
    history.value = []
    await nextTick(() => {
      isRestoring = false
    })
  }

  onConnect((connection) => {
    addEdges({
      ...connection,
      type: 'custom',
    })
  })

  const debouncedOnStateChanged = useDebounceFn(onStateChanged, 200)

  onNodesChange(debouncedOnStateChanged)

  onEdgesChange(debouncedOnStateChanged)

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
    goBack,
    resetPositions,
    save,
  }
})
