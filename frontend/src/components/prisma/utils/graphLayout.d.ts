import type { RunNode, RunEdge } from '@/lib/api/prisma/prisma.interfaces';
export interface LayoutNode {
    id: string;
    position: {
        x: number;
        y: number;
    };
    data: RunNode;
    type: string;
}
export interface LayoutEdge {
    id: string;
    source: string;
    target: string;
    animated: boolean;
}
export declare function computeLayout(nodes: RunNode[], edges: RunEdge[]): {
    nodes: LayoutNode[];
    edges: LayoutEdge[];
};
