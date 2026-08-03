import { describe, it, expect, vi } from 'vitest';
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
    const originalNodes = structuredClone(nodes);
    const result = computeDagreLayout(nodes, []);

    expect(nodes).toEqual(originalNodes); // Input nodes unchanged
    expect(result).not.toBe(nodes); // Returns new array
    expect(result[0]).not.toBe(nodes[0]); // Deep copies objects

    expect(result.length).toBe(2);
    expect(Number.isFinite(result[0].position.x)).toBe(true);
    expect(Number.isFinite(result[0].position.y)).toBe(true);
    expect(Number.isFinite(result[1].position.x)).toBe(true);
    expect(Number.isFinite(result[1].position.y)).toBe(true);

    const diffX = Math.abs(result[0].position.x - result[1].position.x);
    const diffY = Math.abs(result[0].position.y - result[1].position.y);

    // Width is 280, height is 80 (40 header + 0*25 + 40).
    // Ensure they do not overlap
    expect(diffX >= 280 || diffY >= 80).toBe(true);
  });

  it('should fallback to existing positions on layout exceptions/incomplete geometry', () => {
    const nodes: Node<TableNodeData>[] = [
      { id: '1', type: 'tableNode', position: { x: 100, y: 100 }, data: { title: 'users', columns: [], badges: { pk: false, fk: false } } }
    ];

    // To reliably test the fallback mechanism without relying on complex module mocking,
    // we can use a vitest spy on Number.isFinite, which is used to validate geometry.
    // By forcing it to return false for the node's coordinates, we trigger the fallback.
    const isFiniteSpy = vi.spyOn(Number, 'isFinite').mockImplementation((value) => {
      // Force the validGeometry check to fail by returning false when validating
      // the x or y coordinate (or just everything during this test).
      return false;
    });

    try {
      const result = computeDagreLayout(nodes, []);
      // The invalid geometry check fails, so it should return the original positions
      expect(result[0].position.x).toBe(100);
      expect(result[0].position.y).toBe(100);
    } finally {
      isFiniteSpy.mockRestore();
    }
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
