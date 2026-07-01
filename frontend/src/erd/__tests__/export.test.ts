import { describe, it, expect, vi } from 'vitest';
import { exportDDL, exportPlantUml, exportDiagramSvg, downloadText } from '../export';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from '../convert';
import { sourceColumnHandleId, targetColumnHandleId } from '../handleUtils';

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
        sourceHandle: sourceColumnHandleId('user_id'),
        targetHandle: targetColumnHandleId('id'),
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
    expect(ddl).toContain('FOREIGN KEY ("user_id")');
    expect(ddl).toContain('REFERENCES "public.users" ("id")');
    expect(ddl).toContain('ADD CONSTRAINT "fk_2_1"');
    expect(ddl).toContain('FOREIGN KEY (/* source columns */)');
    expect(ddl).toContain('REFERENCES "public.users" (/* target columns */)');
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
  it('should export basic plantuml layout with correct headers', () => {
    const puml = exportPlantUml([], []);
    expect(puml).toContain('@startuml');
    expect(puml).toContain('hide circle');
    expect(puml).toContain('skinparam linetype ortho');
    expect(puml).toContain('@enduml');
  });

  it('should export nullable columns without not-null markers', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
            { column_name: 'email', data_type: 'text', is_not_null: false, is_pk: false },
          ],
          badges: { pk: true, fk: false },
        },
      },
    ];

    const puml = exportPlantUml(nodes, []);
    expect(puml).toContain('entity "public.users" as T_1 {');
    expect(puml).toContain('*id : integer <<not null>>');
    expect(puml).toContain('  email : text');
    expect(puml).toContain('}');
  });

  it('should export nodes and edges to PlantUML format', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          comment: 'User accounts',
          businessGroup: { id: 'bg1', name: 'Core', color: 'blue' },
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true, column_comment: 'PK', example_value: 123 },
            { column_name: 'email', data_type: 'text', is_not_null: true, is_pk: false },
          ],
          indexes: [
            {
              index_name: 'idx_email',
              columns: ['email'],
            } as any
          ],
          badges: { pk: true, fk: false },
        },
      },
      {
        id: '2',
        type: 'tableNode',
        position: { x: 100, y: 0 },
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
        source: '2',
        target: '1',
        label: 'fk_posts_users'
      }
    ];

    const snapshot = {
      indexes: [
        {
          table_oid: 1, // matches node id string '1' after parsing fallback inside export logic, or matches if node.id is '1' in map? The implementation does `String(oid)` so '1' matches `relation_oid: 1`
          relation_oid: 1,
          index_name: 'idx_global_users',
          access_method: 'hash',
          is_unique: true,
          is_primary: false,
          columns: ['email'] // snapshot index format doesn't have columns in DisplayIndex fallback perfectly, but we pass valid object
        } as any
      ]
    };

    const plantUml = exportPlantUml(nodes, edges, snapshot as any);

    expect(plantUml).toContain('@startuml');
    expect(plantUml).toContain('hide circle');
    expect(plantUml).toContain('skinparam linetype ortho');

    // Check table generation
    expect(plantUml).toContain('entity "public.users [Core] (User accounts)" as T_1 {');
    expect(plantUml).toContain('*id (PK) [e.g. 123] : integer <<not null>>');
    expect(plantUml).toContain('email : text <<not null>>');
    expect(plantUml).toContain('<<index>> idx_email');

    // Check snapshot index logic
    expect(plantUml).toContain('<<index>> idx_global_users [hash] (email) unique');

    // Check edges
    expect(plantUml).toContain('T_2 --> T_1 : fk_posts_users');

    expect(plantUml).toContain('@enduml');
  });
});

describe('exportDiagramSvg', () => {
  it('should export nodes and edges to SVG format', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 10, y: 10 },
        data: {
          title: 'public.users',
          businessGroup: { id: 'bg1', name: 'Core', color: 'blue' },
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
          ],
          indexes: [{
            index_name: 'idx_users_id',
            columns: ['id'],
            access_method: 'btree',
          } as any],
          badges: { pk: true, fk: false },
        },
      },
      {
        id: '2',
        type: 'tableNode',
        position: { x: 300, y: 10 },
        data: {
          title: 'public.posts',
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
          ],
          indexes: [],
          badges: { pk: true, fk: false },
        },
      },
    ];

    const edges: Edge[] = [
      {
        id: 'fk1',
        source: '2',
        target: '1',
        label: 'fk_posts_users'
      },
      {
        id: 'fk2',
        source: 'missing_source',
        target: '1',
        label: 'fk_missing_source'
      }
    ];

    const svg = exportDiagramSvg(nodes, edges);

    // Check basic SVG structure
    expect(svg).toContain('<svg xmlns="http://www.w3.org/2000/svg"');
    expect(svg).toContain('<defs><marker id="arrow"');

    // Check elements are rendered
    expect(svg).toContain('>public.users [Core]</text>');
    expect(svg).toContain('>* id: integer not null</text>');
    expect(svg).toContain('>public.posts</text>');

    // Check edge rendering
    expect(svg).toContain('marker-end="url(#arrow)"');
    expect(svg).toContain('>fk_posts_users</text>');
    expect(svg).not.toContain('fk_missing_source');
  });
});

describe('downloadText', () => {
  it('should trigger download with correct content', () => {
    // Mock DOM elements and URL functions
    const mockClick = vi.fn();
    const mockCreateElement = vi.spyOn(document, 'createElement').mockReturnValue({
      href: '',
      download: '',
      click: mockClick,
    } as any);

    const mockCreateObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test-url');
    const mockRevokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

    downloadText('test.sql', 'CREATE TABLE test();');

    expect(mockCreateElement).toHaveBeenCalledWith('a');
    expect(mockCreateObjectURL).toHaveBeenCalled();
    expect(mockClick).toHaveBeenCalled();
    expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:test-url');

    // Clean up
    mockCreateElement.mockRestore();
    mockCreateObjectURL.mockRestore();
    mockRevokeObjectURL.mockRestore();
  });
});

describe('xml and plantuml escaping', () => {
  it('should correctly escape xml and plant text characters', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: 'escape_test_1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.test <>&"\'',
          comment: 'line1\nline2\rline3\\',
          columns: [],
          badges: { pk: false, fk: false },
        },
      },
    ];

    const svg = exportDiagramSvg(nodes, []);
    expect(svg).toContain('public.test &lt;&gt;&amp;&quot;&#39;');

    const plantUml = exportPlantUml(nodes, []);
    expect(plantUml).toContain('public.test &lt;&gt;&amp;&quot;&#39;');
    expect(plantUml).toContain('(line1 line2 line3\\\\)'); // \n \r to space, \\ to \\\\
  });
});

describe('exportDiagramSvg additional edge cases', () => {
  it('should handle undefined columns', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: 'no_columns',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.empty',
          columns: undefined as any,
          badges: { pk: false, fk: false },
        },
      },
    ];
    const svg = exportDiagramSvg(nodes, []);
    expect(svg).toContain('public.empty');
  });

  it('should handle undefined snapshot relation_oid', () => {
    const nodes: Node<TableNodeData>[] = [];
    const snapshot = {
      indexes: [
        {
          relation_oid: undefined,
          table_oid: undefined,
          index_name: 'test_idx',
        } as any
      ]
    };
    const plantUml = exportPlantUml(nodes, [], snapshot as any);
    expect(plantUml).not.toContain('test_idx');
  });

  it('should push index correctly when list already exists in map', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
          ],
          indexes: [],
          badges: { pk: true, fk: false },
        },
      }
    ];

    const snapshot = {
      indexes: [
        {
          table_oid: 1,
          relation_oid: 1,
          index_name: 'idx_users_id_1',
          access_method: 'btree',
          is_unique: false,
          is_primary: false,
        } as any,
        {
          table_oid: 1,
          relation_oid: 1,
          index_name: 'idx_users_id_2',
          access_method: 'btree',
          is_unique: false,
          is_primary: false,
        } as any
      ]
    };

    // exportPlantUml uses groupIndexesByRelation internally
    const plantUml = exportPlantUml(nodes, [], snapshot as any);
    expect(plantUml).toContain('idx_users_id_1');
    expect(plantUml).toContain('idx_users_id_2');
  });
});
