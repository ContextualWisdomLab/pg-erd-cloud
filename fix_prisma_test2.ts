import { exportPrisma } from './frontend/src/erd/prisma';

function relationFixture(relationCount: number) {
  const source = {
    id: 'source',
    position: { x: 0, y: 0 },
    data: {
      title: 'orders',
      badges: { pk: true, fk: true },
      columns: [
        { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
        ...Array.from({ length: relationCount }, (_, index) => ({
          column_name: `fk_${index}`,
          data_type: 'integer',
          is_pk: false,
          is_not_null: true,
        })),
      ],
    },
  };

  const targets = Array.from({ length: relationCount }, (_, index) => ({
    id: `target-${index}`,
    position: { x: index * 10, y: 100 },
    data: {
      title: `target_${index}`,
      badges: { pk: true, fk: false },
      columns: [
        { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
      ],
    },
  }));

  const edges = targets.map((target, index) => ({
    id: `edge-${index}`,
    source: source.id,
    target: target.id,
    sourceHandle: `src-fk_${index}`,
    targetHandle: 'tgt-id',
    label: `orders_target_${index}`,
  }));

  return { nodes: [source, ...targets], edges };
}

const originalArrayIncludes = Array.prototype.includes;

const relationCount = 32;
const { nodes, edges } = relationFixture(relationCount);
let sourceFieldArrayScans = 0;

Array.prototype.includes = function includes(
  this: unknown[],
  searchElement: unknown,
  fromIndex?: number,
): boolean {
  if (
    this.length === 1 &&
    typeof this[0] === 'string' &&
    /^fk_\d+$/.test(this[0]) &&
    typeof searchElement === 'string'
  ) {
    sourceFieldArrayScans += 1;
  }
  return originalArrayIncludes.call(this, searchElement, fromIndex);
};

exportPrisma(nodes as any, edges as any);

console.log('sourceFieldArrayScans', sourceFieldArrayScans);
