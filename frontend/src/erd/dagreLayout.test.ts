import * as dagre from '@dagrejs/dagre';
import type { Edge, Node } from '@xyflow/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { TableNodeData } from './convert';
import { computeDagreLayout } from './dagreLayout';

const NODE_WIDTH = 280;
const HEADER_HEIGHT = 40;
const ROW_HEIGHT = 25;
const FOOTER_HEIGHT = 40;

function calculatedNodeHeight(node: Node<TableNodeData>): number {
  return HEADER_HEIGHT + Math.min(node.data.columns?.length || 0, 25) * ROW_HEIGHT + FOOTER_HEIGHT;
}

describe('dagreLayout', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should layout empty input safely', () => {
    const result = computeDagreLayout([], []);
    expect(result).toEqual([]);
  });

  it('should layout one node safely', () => {
    const nodes: Node<TableNodeData>[] = [
      { id: '1', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'users', columns: [], badges: { pk: false, fk: false } } }
    ];
    const result = computeDagreLayout(nodes, []);
    expect(result.length).toBe(1);
    expect(Number.isFinite(result[0].position.x)).toBe(true);
    expect(Number.isFinite(result[0].position.y)).toBe(true);
  });

  it('should layout disconnected nodes safely and not overlap', () => {
    const nodes: Node<TableNodeData>[] = [
      { id: '1', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'users', columns: [], badges: { pk: false, fk: false } } },
      { id: '2', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'posts', columns: [], badges: { pk: false, fk: false } } }
    ];
    const result = computeDagreLayout(nodes, []);
    expect(result.length).toBe(2);
    expect(Number.isFinite(result[0].position.x)).toBe(true);
    expect(Number.isFinite(result[0].position.y)).toBe(true);
    expect(Number.isFinite(result[1].position.x)).toBe(true);
    expect(Number.isFinite(result[1].position.y)).toBe(true);

    const firstHeight = calculatedNodeHeight(result[0]);
    const secondHeight = calculatedNodeHeight(result[1]);
    const separatedHorizontally =
      result[0].position.x + NODE_WIDTH <= result[1].position.x ||
      result[1].position.x + NODE_WIDTH <= result[0].position.x;
    const separatedVertically =
      result[0].position.y + firstHeight <= result[1].position.y ||
      result[1].position.y + secondHeight <= result[0].position.y;

    expect(separatedHorizontally || separatedVertically).toBe(true);
  });

  it('should layout a directed chain in LR', () => {
    const nodes: Node<TableNodeData>[] = [
      { id: '1', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'users', columns: [], badges: { pk: false, fk: false } } },
      { id: '2', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'posts', columns: [], badges: { pk: false, fk: false } } }
    ];
    const edges: Edge[] = [
      { id: 'e1-2', source: '1', target: '2' }
    ];

    const result = computeDagreLayout(nodes, edges, 'LR');
    expect(result.length).toBe(2);
    expect(result[0].position.x).toBeLessThan(result[1].position.x);
  });

  it('should layout a directed chain in TB', () => {
    const nodes: Node<TableNodeData>[] = [
      { id: '1', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'users', columns: [], badges: { pk: false, fk: false } } },
      { id: '2', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'posts', columns: [], badges: { pk: false, fk: false } } }
    ];
    const edges: Edge[] = [
      { id: 'e1-2', source: '1', target: '2' }
    ];

    const result = computeDagreLayout(nodes, edges, 'TB');
    expect(result.length).toBe(2);
    expect(result[0].position.y).toBeLessThan(result[1].position.y);
  });

  it('should preserve IDs, inputs, and deterministic results', () => {
    const nodes: Node<TableNodeData>[] = [
      { id: '1', type: 'tableNode', position: { x: 7, y: 11 }, data: { title: 'users', columns: [], badges: { pk: false, fk: false } } },
      { id: '2', type: 'tableNode', position: { x: 13, y: 17 }, data: { title: 'posts', columns: [], badges: { pk: false, fk: false } } }
    ];
    const edges: Edge[] = [
      { id: 'e1-2', source: '1', target: '2' }
    ];
    const originalNodes = structuredClone(nodes);
    const originalEdges = structuredClone(edges);

    const result1 = computeDagreLayout(nodes, edges, 'LR');
    const result2 = computeDagreLayout(nodes, edges, 'LR');

    expect(result1[0].id).toBe('1');
    expect(result1[0].data).toEqual(nodes[0].data);
    expect(result1).toEqual(result2);
    expect(nodes).toEqual(originalNodes);
    expect(edges).toEqual(originalEdges);
  });

  it('preserves cloned input positions when Dagre throws', () => {
    const nodes: Node<TableNodeData>[] = [
      { id: '1', type: 'tableNode', position: { x: 23, y: 29 }, data: { title: 'users', columns: [], badges: { pk: false, fk: false } } },
      { id: '2', type: 'tableNode', position: { x: 31, y: 37 }, data: { title: 'posts', columns: [], badges: { pk: false, fk: false } } }
    ];
    vi.spyOn(dagre, 'layout').mockImplementationOnce(() => {
      throw new Error('layout failed');
    });

    const result = computeDagreLayout(nodes, []);

    expect(result.map((node) => node.position)).toEqual(nodes.map((node) => node.position));
    expect(result[0]).not.toBe(nodes[0]);
    expect(result[0].position).not.toBe(nodes[0].position);
  });
});
