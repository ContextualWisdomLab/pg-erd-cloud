import type { Edge, Node } from '@xyflow/react';
import { describe, expect, it } from 'vitest';

import type { TableNodeData } from '../convert';
import { exportDictionaryCsv, exportDictionaryMarkdown } from '../exportDataDictionary';

describe('exportDataDictionary', () => {
  const nodes: Node<TableNodeData>[] = [
    {
      id: 'users',
      type: 'tableNode',
      position: { x: 0, y: 0 },
      data: {
        title: 'public.users',
        comment: 'User accounts',
        badges: { pk: true, fk: false },
        columns: [
          {
            column_name: 'id',
            data_type: 'integer',
            is_pk: true,
            is_not_null: true,
            column_comment: 'Primary Key',
            example_value: 1,
          },
          {
            column_name: 'account_id',
            data_type: 'integer',
            is_pk: false,
            is_not_null: true,
            column_comment: null,
            example_value: 42,
          },
          {
            column_name: 'email',
            data_type: 'varchar',
            is_pk: false,
            is_not_null: true,
            column_comment: null,
            example_value: 'test@example.com',
          },
        ],
      },
    },
    {
      id: 'accounts',
      type: 'tableNode',
      position: { x: 0, y: 0 },
      data: {
        title: 'public.accounts',
        comment: null,
        badges: { pk: true, fk: false },
        columns: [
          {
            column_name: 'id',
            data_type: 'integer',
            is_pk: true,
            is_not_null: true,
            column_comment: null,
            example_value: 1,
          },
        ],
      },
    },
    {
      id: 'empty_table',
      type: 'tableNode',
      position: { x: 0, y: 0 },
      data: {
        title: 'empty_table',
        comment: null,
        badges: { pk: false, fk: false },
        columns: [],
      },
    },
  ];

  const edges: Edge[] = [
    {
      id: 'fk_users_accounts',
      source: 'users',
      target: 'accounts',
      data: { sourceColumns: ['account_id'], targetColumns: ['id'] },
    },
  ];

  it('exports table and column metadata to CSV', () => {
    const csv = exportDictionaryCsv(nodes, edges);

    expect(csv).toContain('"Table Name","Table Comment","Column Name","Data Type","PK","FK","Not Null","Column Comment","Example Value"');
    expect(csv).toContain('"public.users","User accounts","id","integer","Y","N","Y","Primary Key","1"');
    expect(csv).toContain('"public.users","User accounts","account_id","integer","N","Y","Y","","42"');
    expect(csv).toContain('"public.users","User accounts","email","varchar","N","N","Y","","test@example.com"');
    expect(csv).toContain('"empty_table","","","","","","","",""');
  });

  it('handles empty CSV exports', () => {
    expect(exportDictionaryCsv([], edges)).toBe(
      '"Table Name","Table Comment","Column Name","Data Type","PK","FK","Not Null","Column Comment","Example Value"',
    );
  });

  it('neutralizes CSV formula injection and normalizes control characters', () => {
    const csv = exportDictionaryCsv(
      [
        {
          id: 'attack',
          type: 'tableNode',
          position: { x: 0, y: 0 },
          data: {
            title: '=HYPERLINK("https://example.invalid")',
            comment: '@note\r\nsecond line',
            badges: { pk: false, fk: false },
            columns: [
              {
                column_name: '+cmd',
                data_type: '-integer',
                is_pk: false,
                is_not_null: false,
                column_comment: '@comment',
                example_value: '\t=2+2',
              },
            ],
          },
        },
      ],
      [],
    );

    expect(csv).toContain('"\'=HYPERLINK(""https://example.invalid"")"');
    expect(csv).toContain('"\'@note second line"');
    expect(csv).toContain('"\'+cmd"');
    expect(csv).toContain('"\'-integer"');
    expect(csv).toContain('"\'@comment"');
    expect(csv).toContain('"\' =2+2"');
  });

  it('exports table and column metadata to Markdown', () => {
    const markdown = exportDictionaryMarkdown(nodes, edges);

    expect(markdown).toContain('# Data Dictionary');
    expect(markdown).toContain('## Table: public.users (User accounts)');
    expect(markdown).toContain('| id | integer | Y | N | Y | Primary Key | 1 |');
    expect(markdown).toContain('| account_id | integer | N | Y | Y |  | 42 |');
    expect(markdown).toContain('## Table: empty_table');
    expect(markdown).toContain('No columns.');
  });

  it('escapes Markdown table breakers and HTML-like content', () => {
    const markdown = exportDictionaryMarkdown(
      [
        {
          id: 'danger',
          type: 'tableNode',
          position: { x: 0, y: 0 },
          data: {
            title: 'orders|<script>\nnext',
            comment: '<b>note</b>',
            badges: { pk: false, fk: false },
            columns: [
              {
                column_name: 'name|x',
                data_type: 'text',
                is_pk: false,
                is_not_null: false,
                column_comment: 'see [docs](javascript:alert(1))',
                example_value: '<img src=x onerror=alert(1)>',
              },
            ],
          },
        },
      ],
      [],
    );

    expect(markdown).toContain('## Table: orders\\|&lt;script&gt; next (&lt;b&gt;note&lt;/b&gt;)');
    expect(markdown).toContain('name\\|x');
    expect(markdown).toContain('see \\[docs\\]\\(javascript:alert\\(1\\)\\)');
    expect(markdown).toContain('&lt;img src=x onerror=alert\\(1\\)&gt;');
    expect(markdown).not.toContain('<script>');
    expect(markdown).not.toContain('<img');
  });

  it('handles empty Markdown exports', () => {
    expect(exportDictionaryMarkdown([], edges)).toBe('# Data Dictionary\n\nNo tables found.');
  });
});
