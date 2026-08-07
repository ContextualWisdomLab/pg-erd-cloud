import { describe, expect, it } from 'vitest';

import type { Node } from '@xyflow/react';
import type { TableNodeData } from '../convert';
import { exportDiagramSvg } from '../export';

describe('exportDiagramSvg XSS Protection', () => {
  it('escapes user input in SVG exports', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'table',
        position: { x: 0, y: 0 },
        data: {
          title: '</text><script>alert(1)</script><text>',
          badges: { pk: false, fk: false },
          columns: [{ column_name: 'col1', data_type: 'text', column_comment: '', is_pk: false, is_not_null: false }],
        },
      },
    ];
    const svg = exportDiagramSvg(nodes, []);
    expect(svg).toContain('&lt;/text&gt;&lt;script&gt;alert(1)&lt;/script&gt;&lt;text&gt;');
    expect(svg).not.toContain('<script>');
  });

  it('sanitizes XML structures in edges', () => {
    const svg = exportDiagramSvg(
      [
        {
          id: '1',
          type: 'table',
          position: { x: 0, y: 0 },
          data: { title: 't1', columns: [], badges: { pk: false, fk: false } },
        },
        {
          id: '2',
          type: 'table',
          position: { x: 100, y: 0 },
          data: { title: 't2', columns: [], badges: { pk: false, fk: false } },
        },
      ],
      [
        {
          id: 'e1',
          source: '1',
          target: '2',
          label: '<svg onload="alert(1)">',
        },
      ]
    );
    expect(svg).toContain('&lt;svg onload=&quot;alert(1)&quot;&gt;');
    expect(svg).not.toContain('<svg onload');
  });

  it('rejects XSS vectors in node position attributes', () => {
    const nodes = [
      {
        id: '1',
        type: 'table',
        position: { x: '" onmouseover="alert(\'XSS\')', y: '0' },
        data: { title: 't1', columns: [], badges: { pk: false, fk: false } },
      },
    ] as any;
    const svg = exportDiagramSvg(nodes, []);
    expect(svg).not.toContain('onmouseover');
    // Using Number logic forces string positions to evaluate to NaN (which becomes 0 with the || 0 fallback)
    expect(svg).toContain('x="40"'); // 0 + offsetX (padding is 40)
  });
});
