import type { Edge, Node } from '@xyflow/react'
import { describe, expect, it } from 'vitest'

import { inferRelationships } from '../autoInfer'
import { exportDbml } from '../dbml'
import type { TableNodeData } from '../convert'
import {
  exportDDL,
  exportDiagramSvg,
  exportPlantUml,
} from '../export'
import {
  exportDictionaryCsv,
  exportDictionaryMarkdown,
} from '../exportDataDictionary'
import { exportMermaid } from '../mermaid'
import {
  findSearchMatchedNodeIds,
  tableNodeMatchesSearch,
} from '../search'

function node(
  id: string,
  title: string,
  columns: TableNodeData['columns'] = [],
  extra: Partial<TableNodeData> = {},
): Node<TableNodeData> {
  return {
    id,
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: {
      title,
      columns,
      badges: { pk: false, fk: false },
      ...extra,
    },
  }
}

describe('coverage edge contracts', () => {
  it('covers empty identifiers, empty types, schema variants, and incomplete DBML relations', () => {
    const parent = node('parent', 'sales.parent', [
      { column_name: '', data_type: '', is_not_null: false, is_pk: false },
    ])
    const child = node('child', 'child', [
      { column_name: 'parent_id', data_type: 'int', is_not_null: false, is_pk: false },
    ])
    const edges: Edge[] = [
      { id: 'missing', source: 'missing', target: 'parent' },
      { id: 'partial-data', source: 'child', target: 'parent', data: { sourceColumns: ['parent_id'] } },
      { id: 'empty-data', source: 'child', target: 'parent', data: { sourceColumns: [], targetColumns: [] } },
      { id: 'handles', source: 'child', target: 'parent', sourceHandle: 'src-parent_id', targetHandle: 'tgt-' },
    ]

    const dbml = exportDbml([parent, child, node('empty', '', [])], edges)
    expect(dbml).toContain('Table sales.parent')
    expect(dbml).toContain('Table  {')
    expect(dbml).toContain(' varchar')
    expect(dbml).toContain('Ref: child.parent_id > sales.parent.')
  })

  it('covers DDL defensive fallbacks and column inference without handles', () => {
    const parent = node('parent', '', [
      { column_name: '', data_type: undefined as any, is_not_null: false, is_pk: true },
    ])
    const child = node('child', '', [
      { column_name: 'parent_id', data_type: '', is_not_null: false, is_pk: false },
    ])
    const noColumns = node('none', 'none') as any
    noColumns.data.columns = undefined

    const ddl = exportDDL(
      [parent, child, noColumns],
      [{ id: 'fallback', source: 'child', target: 'parent' }],
    )
    expect(ddl).toContain('CREATE TABLE "parent"')
    expect(ddl).toContain('"unnamed" text')
    expect(ddl).toContain('FOREIGN KEY ("parent_id")')
    expect(ddl).toContain('REFERENCES "parent" ("unnamed")')

    const nullIdentifierDdl = exportDDL([
      node('null-id', 'null-id', [
        { column_name: null as any, data_type: 'text', is_not_null: false, is_pk: false },
      ]),
    ], [])
    expect(nullIdentifierDdl).toContain('"unnamed" text')

    const missingColumnsDdl = exportDDL(
      [noColumns, { ...noColumns, id: 'other', data: { ...noColumns.data } }],
      [{ id: 'missing-columns', source: 'none', target: 'other' }],
    )
    expect(missingColumnsDdl).toContain('/* source columns */')
  })

  it('covers nullable export metadata and snapshot index variants', () => {
    const withoutColumns = node('empty', '', []) as any
    withoutColumns.data.columns = undefined
    withoutColumns.data.comment = undefined
    const rich = node(
      'rich-id',
      '',
      [{
        column_name: 'value',
        data_type: undefined as any,
        is_not_null: false,
        is_pk: false,
        column_comment: undefined,
        example_value: undefined,
      }],
      { comment: '', indexes: [] },
    )
    const snapshotNode = { ...rich, id: '7' }
    const snapshot = {
      indexes: [
        { relation_oid: 7, index_name: 'no_method' },
        { table_oid: 7, index_name: 'with_ext', access_method: 'gist', access_method_extension: 'postgis', operator_class_extensions: [] },
        { table_oid: 7, index_name: 'primary', access_method: 'btree', access_method_extension: null, operator_class_extensions: undefined, is_primary: true },
      ],
    }

    expect(exportDictionaryCsv([withoutColumns, rich], [])).toContain('"empty"')
    expect(exportDictionaryMarkdown([withoutColumns, rich], [])).toContain('## Table: empty')
    expect(exportPlantUml([withoutColumns, snapshotNode], [{ id: 'plain', source: 'empty', target: '7' }], snapshot as any)).toContain('primary [btree] primary')
    expect(exportDiagramSvg([withoutColumns, snapshotNode], [{ id: 'plain', source: 'empty', target: '7' }], snapshot as any)).toContain('<svg')
  })

  it('covers dictionary edge aggregation, handle fallback, null values, and repeated sources', () => {
    const source = node('source', '', [
      { column_name: 'first_id', data_type: 'int', is_not_null: false, is_pk: false, example_value: null },
      { column_name: 'second_id', data_type: 'int', is_not_null: false, is_pk: false, example_value: undefined },
    ])
    const edges: Edge[] = [
      { id: 'blank', source: 'source', target: 'target', data: { sourceColumns: ['', 'first_id'] } },
      { id: 'handle', source: 'source', target: 'target', sourceHandle: 'src-c-0073-0065-0063-006f-006e-0064-005f-0069-0064' },
      { id: 'none', source: 'source', target: 'target' },
    ]
    const csv = exportDictionaryCsv([source], edges)
    const markdown = exportDictionaryMarkdown([source], edges)
    expect(csv).toContain('"first_id","int","N","Y"')
    expect(csv).toContain('"second_id","int","N","Y"')
    expect(markdown).toContain('| first_id | int | N | Y |')
    expect(markdown).toContain('| second_id | int | N | Y |')
  })

  it('covers search comment matches and direct empty term arrays', () => {
    const searchable = node('search', 'table', [
      { column_name: 'id', data_type: 'uuid', is_not_null: false, is_pk: false, column_comment: 'External reference' },
    ])
    expect(tableNodeMatchesSearch(searchable, ['external'])).toBe(true)
    expect(tableNodeMatchesSearch(searchable, [])).toBe(false)
    expect([...findSearchMatchedNodeIds([searchable], 'external')]).toEqual(['search'])
  })

  it('covers inference duplicate names, sanitized lookup misses, and empty targets', () => {
    const duplicated = node('first', 'users', [])
    const ignoredDuplicate = node('second', 'users', [
      { column_name: 'id', data_type: 'int', is_not_null: true, is_pk: true },
    ])
    const emptyTarget = node('empty-target', 'category', [])
    const source = node('source', 'items', [
      { column_name: 'category_id', data_type: 'int', is_not_null: false, is_pk: false },
      { column_name: 'users_id', data_type: 'int', is_not_null: false, is_pk: false },
    ])
    expect(inferRelationships([duplicated, ignoredDuplicate, emptyTarget, source])).toEqual([])

    const unsafeTarget = node('unsafe', 'bad-name', [])
    const unsafeSource = node('unsafe-source', 'events', [
      { column_name: 'bad-name_id', data_type: 'int', is_not_null: false, is_pk: false },
    ])
    expect(inferRelationships([unsafeTarget, unsafeSource])).toEqual([])
  })

  it('covers Mermaid non-matching handles and false FK badges', () => {
    const source = node('source', 'source', [
      { column_name: 'id', data_type: 'int', is_not_null: false, is_pk: false },
    ])
    const target = node('target', 'target', [], { badges: { pk: false, fk: false } })
    const output = exportMermaid(
      [source, target],
      [{ id: 'edge', source: 'source', target: 'target', sourceHandle: 'custom', targetHandle: 'custom' }],
    )
    expect(output).toContain('"target" ||--o{ "source"')
    expect(output).not.toContain(' FK')
  })
})
