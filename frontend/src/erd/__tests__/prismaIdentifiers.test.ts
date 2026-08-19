import { describe, expect, it } from 'vitest';

import {
  isPrismaIdentifier,
  isReservedPrismaName,
  PRISMA_IDENTIFIER_CONTRACT_VERSION,
} from '../prismaIdentifierContract';
import {
  allocatePrismaIdentifiers,
  buildPrismaManifest,
  preferredPrismaName,
} from '../prismaIdentifiers';

describe('preferredPrismaName', () => {
  it('keeps a legal identifier', () => {
    expect(preferredPrismaName('users')).toBe('users');
  });

  it('prefixes leading digits without colliding reserved escapes', () => {
    expect(preferredPrismaName('123invalid')).toBe('M_123invalid');
  });

  it('escapes reserved schema keywords with a trailing underscore', () => {
    expect(preferredPrismaName('model')).toBe('model_');
    expect(preferredPrismaName('Model')).toBe('Model_');
    expect(preferredPrismaName('MODEL')).toBe('MODEL_');
  });

  it('does not map reserved model onto an existing M_model source', () => {
    expect(preferredPrismaName('model')).not.toBe(preferredPrismaName('M_model'));
    expect(preferredPrismaName('M_model')).toBe('M_model');
  });

  it('collapses punctuation and whitespace to underscores', () => {
    expect(preferredPrismaName('order-item')).toBe('order_item');
    expect(preferredPrismaName('order item')).toBe('order_item');
  });

  it('orders Unicode sources by code point for cross-runtime determinism', () => {
    const result = allocatePrismaIdentifiers([
      { key: 'accent', kind: 'model', namespace: 'models', source: 'é' },
      { key: 'sharp-s', kind: 'model', namespace: 'models', source: 'ß' },
    ]);

    expect(result.names.get('sharp-s')).toBe('unnamed');
    expect(result.names.get('accent')).toBe('unnamed_2');
  });

  it('uses unnamed for Korean, emoji, and empty sources', () => {
    expect(preferredPrismaName('사용자')).toBe('unnamed');
    expect(preferredPrismaName('📦')).toBe('unnamed');
    expect(preferredPrismaName('   ')).toBe('unnamed');
  });
});

describe('allocatePrismaIdentifiers', () => {
  it('allocates reserved names and M_model without collision', () => {
    const result = allocatePrismaIdentifiers([
      { key: 'a', kind: 'model', namespace: 'models', source: 'model' },
      { key: 'b', kind: 'model', namespace: 'models', source: 'Model' },
      { key: 'c', kind: 'model', namespace: 'models', source: 'MODEL' },
      { key: 'd', kind: 'model', namespace: 'models', source: 'M_model' },
    ]);

    expect(result.ok).toBe(true);
    const generated = [...result.names.values()];
    expect(new Set(generated).size).toBe(4);
    expect(result.names.get('d')).toBe('M_model');
    expect(result.names.get('a')).toBe('model_');
  });

  it('makes punctuation collisions deterministic under reordering', () => {
    const sources = ['order-item', 'order item', 'order_item'];
    const forward = allocatePrismaIdentifiers(
      sources.map((source, index) => ({
        key: `k${index}`,
        kind: 'model',
        namespace: 'models',
        source,
      })),
    );
    const reverse = allocatePrismaIdentifiers(
      [...sources].reverse().map((source, index) => ({
        key: `k${index}`,
        kind: 'model',
        namespace: 'models',
        source,
      })),
    );

    expect(forward.ok).toBe(true);
    expect(reverse.ok).toBe(true);
    const bySource = (allocation: typeof forward) =>
      Object.fromEntries(allocation.mappings.map((row) => [row.source, row.generated]));
    expect(bySource(forward)).toEqual(bySource(reverse));
    expect(new Set(forward.names.values()).size).toBe(3);
  });

  it('keeps NFC and NFD Hangul distinguishable via unique generated names', () => {
    const nfc = '가'.normalize('NFC');
    const nfd = '가'.normalize('NFD');
    const result = allocatePrismaIdentifiers([
      { key: 'nfc', kind: 'model', namespace: 'models', source: nfc },
      { key: 'nfd', kind: 'model', namespace: 'models', source: nfd },
    ]);

    expect(result.ok).toBe(true);
    expect(result.names.get('nfc')).not.toBe(result.names.get('nfd'));
    expect(isPrismaIdentifier(result.names.get('nfc') ?? '')).toBe(true);
    expect(isPrismaIdentifier(result.names.get('nfd') ?? '')).toBe(true);
  });

  it('fails closed when the attempt bound is exhausted', () => {
    const result = allocatePrismaIdentifiers(
      [
        { key: 'a', kind: 'field', namespace: 'fields:users', source: 'id' },
        { key: 'b', kind: 'field', namespace: 'fields:users', source: 'id' },
      ],
      0,
    );

    expect(result.ok).toBe(false);
    expect(result.names.size).toBe(1);
  });

  it('records the pinned contract version on the manifest', () => {
    const allocated = allocatePrismaIdentifiers([
      { key: 'users', kind: 'model', namespace: 'models', source: 'users' },
    ]);
    const manifest = buildPrismaManifest(allocated.mappings);
    expect(manifest.contractVersion).toBe(PRISMA_IDENTIFIER_CONTRACT_VERSION);
    expect(manifest.mappings[0]).toEqual({
      kind: 'model',
      namespace: 'models',
      source: 'users',
      generated: 'users',
    });
  });

  it('honors an explicit preferred name when it is still unique', () => {
    const result = allocatePrismaIdentifiers([
      {
        key: 'a',
        kind: 'model',
        namespace: 'models',
        source: 'order items',
        preferred: 'OrderItems',
      },
    ]);
    expect(result.ok).toBe(true);
    expect(result.names.get('a')).toBe('OrderItems');
  });

  it('separates identical sources across namespaces', () => {
    const result = allocatePrismaIdentifiers([
      { key: 'm', kind: 'model', namespace: 'models', source: 'id' },
      { key: 'f', kind: 'field', namespace: 'fields:users', source: 'id' },
    ]);
    expect(result.ok).toBe(true);
    expect(result.names.get('m')).toBe('id');
    expect(result.names.get('f')).toBe('id');
  });

  it('treats Prisma Client reserved names as reserved', () => {
    expect(isReservedPrismaName('class')).toBe(true);
    expect(isReservedPrismaName('PrismaClient')).toBe(true);
    expect(isReservedPrismaName('String')).toBe(true);
    expect(isReservedPrismaName('users')).toBe(false);
  });
});
