import { describe, it, expect } from 'vitest';
import { computeDagreLayout } from './dagreLayout';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from './convert';

describe('dagreLayout', () => {
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

    const diffX = Math.abs(result[0].position.x - result[1].position.x);
    const diffY = Math.abs(result[0].position.y - result[1].position.y);
    expect(diffX > 0 || diffY > 0).toBe(true);
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

  it('should preserve IDs and data immutability and be deterministic', () => {
    const nodes: Node<TableNodeData>[] = [
      { id: '1', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'users', columns: [], badges: { pk: false, fk: false } } },
      { id: '2', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'posts', columns: [], badges: { pk: false, fk: false } } }
    ];
    const edges: Edge[] = [
      { id: 'e1-2', source: '1', target: '2' }
    ];
    const result1 = computeDagreLayout(nodes, edges, 'LR');
    const result2 = computeDagreLayout(nodes, edges, 'LR');

    expect(result1[0].id).toBe('1');
    expect(result1[0].data).toEqual(nodes[0].data);
    expect(result1).toEqual(result2);
  });
});
