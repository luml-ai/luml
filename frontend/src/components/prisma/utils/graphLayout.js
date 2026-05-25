import dagre from 'dagre';
export function computeLayout(nodes, edges) {
    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: 'TB', nodesep: 40, ranksep: 60 });
    for (const node of nodes) {
        const hasMetric = node.node_type === 'run' &&
            node.result?.artifacts?.metric !== undefined &&
            node.result?.artifacts?.metric !== null;
        g.setNode(node.id, { width: 200, height: hasMetric ? 100 : 80 });
    }
    for (const edge of edges) {
        g.setEdge(edge.from_node_id, edge.to_node_id);
    }
    dagre.layout(g);
    const layoutNodes = nodes.map((node) => {
        const pos = g.node(node.id);
        const halfH = pos.height / 2;
        return {
            id: node.id,
            position: { x: pos.x - 100, y: pos.y - halfH },
            data: node,
            type: 'graphNode',
        };
    });
    const layoutEdges = edges.map((edge) => ({
        id: `e${edge.from_node_id}-${edge.to_node_id}`,
        source: edge.from_node_id,
        target: edge.to_node_id,
        animated: nodes.find((n) => n.id === edge.to_node_id)?.status === 'running',
    }));
    return { nodes: layoutNodes, edges: layoutEdges };
}
