import { describe, it, expect, vi } from 'vitest';
import { exportDDL, exportPlantUml, exportDiagramSvg, downloadText } from '../export';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('exportDDL', () => {
  it('should export basic table DDL with primary key', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
            { column_name: 'name', data_type: 'text', is_not_null: false, is_pk: false },
          ],
          badges: { pk: true, fk: false },
        },
      },
    ];
    const edges: Edge[] = [];

    const ddl = exportDDL(nodes, edges);
    expect(ddl).toContain('CREATE TABLE "public.users"');
    expect(ddl).toContain('"id" integer NOT NULL');
    expect(ddl).toContain('"name" text');
    expect(ddl).toContain('PRIMARY KEY ("id")');
  });

  it('should export table without primary key', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '2',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.events',
          columns: [
            { column_name: 'event_name', data_type: 'varchar(255)', is_not_null: true, is_pk: false },
          ],
          badges: { pk: false, fk: false },
        },
      },
    ];
    const edges: Edge[] = [];

    const ddl = exportDDL(nodes, edges);
    expect(ddl).toContain('CREATE TABLE "public.events"');
    expect(ddl).toContain('"event_name" varchar(255) NOT NULL');
    expect(ddl).not.toContain('PRIMARY KEY');
  });

  it('should format foreign keys correctly', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          columns: [{ column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true }],
          badges: { pk: true, fk: false },
        },
      },
      {
        id: '2',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.posts',
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
            { column_name: 'user_id', data_type: 'integer', is_not_null: true, is_pk: false },
          ],
          badges: { pk: true, fk: true },
        },
      },
    ];
    const edges: Edge[] = [
      {
        id: 'fk1',
        source: '2', // source is the table with foreign key
        target: '1', // target is the referenced table
        label: 'fk_posts_users',
      },
      {
        id: 'fk2',
        source: '2',
        target: '1',
        // missing label to test auto generated constraint name fallback
      }
    ];

    const ddl = exportDDL(nodes, edges);
    expect(ddl).toContain('ALTER TABLE "public.posts"');
    expect(ddl).toContain('ADD CONSTRAINT "fk_posts_users"');
    expect(ddl).toContain('ADD CONSTRAINT "fk_2_1"');
    expect(ddl).toContain('REFERENCES "public.users"');
  });

  it('should not throw if foreign key source or target is missing', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          columns: [{ column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true }],
          badges: { pk: true, fk: false },
        },
      },
    ];
    const edges: Edge[] = [
      {
        id: 'fk1',
        source: '1',
        target: '2', // Target node '2' does not exist
        label: 'fk_missing_target',
      },
      {
        id: 'fk2',
        source: '3', // Source node '3' does not exist
        target: '1',
        label: 'fk_missing_source',
      }
    ];

    const ddl = exportDDL(nodes, edges);
    expect(ddl).not.toContain('fk_missing_target');
    expect(ddl).not.toContain('fk_missing_source');
  });

  it('should export indexes correctly and not emit duplicate index names', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
            { column_name: 'email', data_type: 'text', is_not_null: true, is_pk: false },
            { column_name: 'status', data_type: 'text', is_not_null: false, is_pk: false },
          ],
          indexes: [
            {
              index_name: 'idx_users_email',
              columns: ['email'],
              access_method: 'btree',
            },
            {
              index_name: 'idx_users_email', // Duplicate should be skipped
              columns: ['email'],
              access_method: 'btree',
            },
            {
              index_name: 'idx_users_status',
              columns: ['status'],
              // test default access method fallback
            },
            {
              index_name: 'idx_empty',
              columns: [], // should skip empty columns
            }
          ] as any[],
          badges: { pk: true, fk: false },
        },
      },
    ];

    const ddl = exportDDL(nodes, []);
    expect(ddl).toContain('-- Indexes');
    expect(ddl).toContain('CREATE INDEX CONCURRENTLY "idx_users_email" ON "public.users" USING btree ("email");');

    // Using string match to ensure it only appears once
    const matches = ddl.match(/CREATE INDEX CONCURRENTLY "idx_users_email"/g);
    expect(matches?.length).toBe(1);

    expect(ddl).toContain('CREATE INDEX CONCURRENTLY "idx_users_status" ON "public.users" USING btree ("status");');
    expect(ddl).not.toContain('idx_empty');
  });

  it('should fallback to node.id for table name if title is not provided', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: 'fallback_table',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: '', // empty title
          columns: [],
          badges: { pk: false, fk: false },
        },
      },
    ];

    const ddl = exportDDL(nodes, []);
    expect(ddl).toContain('CREATE TABLE "fallback_table"');
  });

  it('should correctly quote sql identifiers', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'User "Account"',
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
            { column_name: 'email "address"', data_type: 'text', is_not_null: false, is_pk: false },
          ],
          indexes: [
            {
              index_name: 'idx_"user"_account',
              columns: ['email "address"'],
              access_method: 'btree',
            }
          ] as any[],
          badges: { pk: true, fk: false },
        },
      },
    ];

    const ddl = exportDDL(nodes, []);
    expect(ddl).toContain('CREATE TABLE "User ""Account"""');
    expect(ddl).toContain('"email ""address""" text');
    expect(ddl).toContain('CREATE INDEX CONCURRENTLY "idx_""user""_account" ON "User ""Account""" USING btree ("email ""address""");');
  });

  it('should correctly fallback invalid sql data types or access methods', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.data',
          columns: [
            { column_name: 'valid_type', data_type: 'integer', is_not_null: false, is_pk: false },
            { column_name: 'invalid_type', data_type: 'drop table users;', is_not_null: false, is_pk: false },
          ],
          indexes: [
            {
              index_name: 'idx_invalid_method',
              columns: ['invalid_type'],
              access_method: 'delete from users', // invalid access method
            }
          ] as any[],
          badges: { pk: false, fk: false },
        },
      },
    ];

    const ddl = exportDDL(nodes, []);
    // sqlDataType invalid input fallback is 'text'
    expect(ddl).toContain('"invalid_type" text');
    expect(ddl).toContain('"valid_type" integer');
    // sqlAccessMethod invalid input fallback is 'btree'
    expect(ddl).toContain('CREATE INDEX CONCURRENTLY "idx_invalid_method" ON "public.data" USING btree ("invalid_type");');
  });
});

describe('exportPlantUml', () => {
  it('should export basic table and columns to PlantUML', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
            { column_name: 'name', data_type: 'text', is_not_null: false, is_pk: false },
          ],
          badges: { pk: true, fk: false },
        },
      },
    ];

    const uml = exportPlantUml(nodes, []);
    expect(uml).toContain('@startuml');
    expect(uml).toContain('entity "public.users" as T_1 {');
    expect(uml).toContain('*id : integer <<not null>>');
    expect(uml).toContain('name : text');
    expect(uml).toContain('}');
    expect(uml).toContain('@enduml');
  });

  it('should export foreign key edges to PlantUML', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: { title: 'users', columns: [], badges: { pk: false, fk: false } },
      },
      {
        id: '2',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: { title: 'posts', columns: [], badges: { pk: false, fk: false } },
      },
    ];
    const edges: Edge[] = [
      { id: 'e1', source: '2', target: '1', label: 'fk_user' },
    ];

    const uml = exportPlantUml(nodes, edges);
    expect(uml).toContain('T_2 --> T_1 : fk_user');
  });
});

describe('exportDiagramSvg', () => {
  it('should export nodes and edges to SVG', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 10, y: 10 },
        data: {
          title: 'public.users',
          columns: [{ column_name: 'id', data_type: 'int', is_not_null: true, is_pk: true }],
          badges: { pk: true, fk: false },
        },
      },
      {
        id: '2',
        type: 'tableNode',
        position: { x: 200, y: 10 },
        data: {
          title: 'public.posts',
          businessGroup: { id: 'bg1', name: 'Sales', color: '#ff0000' },
          columns: [{ column_name: 'user_id', data_type: 'int', is_not_null: true, is_pk: false }],
          badges: { pk: false, fk: true },
        },
      },
    ];
    const edges: Edge[] = [
      { id: 'e1', source: '2', target: '1', label: 'fk_user' },
    ];

    const svg = exportDiagramSvg(nodes, edges);
    expect(svg).toContain('<svg xmlns="http://www.w3.org/2000/svg"');
    expect(svg).toContain('public.users');
    expect(svg).toContain('* id: int not null');
    expect(svg).toContain('public.posts [Sales]');
    expect(svg).toContain('user_id: int not null');
    expect(svg).toContain('fk_user');
    expect(svg).toContain('</svg>');
  });
});


describe('downloadText', () => {
  it('should create object URL and trigger download', () => {
    // Setup a minimal mock for document and URL within the scope of this test
    // that doesn't leak or completely replace the global object if already present

    // We only mock what we need. Note: In vitest with jsdom/happy-dom, document exists.
    // If we're in pure node, document might not exist.
    const originalCreateObjectURL = globalThis.URL?.createObjectURL;
    const originalRevokeObjectURL = globalThis.URL?.revokeObjectURL;

    const createObjUrl = vi.fn().mockReturnValue('blob:test');
    const revokeObjUrl = vi.fn();

    // Using Object.defineProperty to safely mock the methods, even if readonly
    Object.defineProperty(globalThis.URL, 'createObjectURL', { value: createObjUrl, configurable: true });
    Object.defineProperty(globalThis.URL, 'revokeObjectURL', { value: revokeObjUrl, configurable: true });

    const mockClick = vi.fn();
    const mockLink = { href: '', download: '', click: mockClick };

    // Mock the DOM interaction
    let createElementSpy;
    if (typeof document !== 'undefined') {
      createElementSpy = vi.spyOn(document, 'createElement').mockReturnValue(mockLink as any);
    } else {
      // Very basic fallback if document doesn't exist
      (globalThis as any).document = { createElement: vi.fn().mockReturnValue(mockLink) } as any;
    }

    downloadText('test.sql', 'SELECT 1;');

    expect(createObjUrl).toHaveBeenCalled();
    if (createElementSpy) {
        expect(createElementSpy).toHaveBeenCalledWith('a');
        createElementSpy.mockRestore();
    }
    expect(mockLink.download).toBe('test.sql');
    expect(mockLink.href).toBe('blob:test');
    expect(mockClick).toHaveBeenCalled();
    expect(revokeObjUrl).toHaveBeenCalledWith('blob:test');

    // Clean up our mocks
    if (originalCreateObjectURL !== undefined) {
        Object.defineProperty(globalThis.URL, 'createObjectURL', { value: originalCreateObjectURL, configurable: true });
    }
    if (originalRevokeObjectURL !== undefined) {
        Object.defineProperty(globalThis.URL, 'revokeObjectURL', { value: originalRevokeObjectURL, configurable: true });
    }
  });
});
