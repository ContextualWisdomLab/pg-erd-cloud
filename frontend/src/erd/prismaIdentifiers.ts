import {
  PRISMA_IDENTIFIER_CONTRACT_VERSION,
  PRISMA_IDENTIFIER_MAX_ATTEMPTS,
  isPrismaIdentifier,
  isReservedPrismaName,
} from "./prismaIdentifierContract";

export type PrismaIdentifierKind = "model" | "field" | "relation";

export type PrismaIdentifierMapping = {
  kind: PrismaIdentifierKind;
  namespace: string;
  source: string;
  generated: string;
};

export type PrismaIdentifierRequest = {
  key: string;
  kind: PrismaIdentifierKind;
  namespace: string;
  source: string;
  preferred?: string;
};

export type PrismaIdentifierAllocation = {
  ok: boolean;
  names: Map<string, string>;
  mappings: PrismaIdentifierMapping[];
};

/**
 * Collapse a database or canvas name to a Prisma grammar candidate.
 *
 * Non-ASCII, punctuation, and whitespace become `_`. Leading digits use the
 * `M_` prefix. Reserved names take a trailing `_` so they do not collide with
 * a source already named `M_model`.
 */
export function preferredPrismaName(source: string): string {
  const normalized = source.normalize("NFC");
  let candidate = normalized.replace(/[^A-Za-z0-9_]+/g, "_");
  candidate = candidate.replace(/_+/g, "_").replace(/^_+|_+$/g, "");
  if (candidate.length === 0) {
    candidate = "unnamed";
  }
  if (!/^[A-Za-z]/.test(candidate)) {
    candidate = `M_${candidate}`;
  }
  if (isReservedPrismaName(candidate) || !isPrismaIdentifier(candidate)) {
    candidate = `${candidate}_`;
  }
  return candidate;
}

function compareRequests(
  left: PrismaIdentifierRequest,
  right: PrismaIdentifierRequest,
): number {
  const sourceOrder = left.source.localeCompare(right.source);
  if (sourceOrder !== 0) {
    return sourceOrder;
  }
  const namespaceOrder = left.namespace.localeCompare(right.namespace);
  if (namespaceOrder !== 0) {
    return namespaceOrder;
  }
  return left.key.localeCompare(right.key);
}

/**
 * Allocate deterministic, collision-free Prisma identifiers.
 *
 * Requests are sorted by source text so input order cannot change the mapping.
 * A taken or reserved candidate receives `_2`, `_3`, … until the attempt bound.
 */
export function allocatePrismaIdentifiers(
  requests: PrismaIdentifierRequest[],
  maxAttempts: number = PRISMA_IDENTIFIER_MAX_ATTEMPTS,
): PrismaIdentifierAllocation {
  const names = new Map<string, string>();
  const mappings: PrismaIdentifierMapping[] = [];
  const usedByNamespace = new Map<string, Set<string>>();
  const ordered = [...requests].sort(compareRequests);

  for (const request of ordered) {
    const used = usedByNamespace.get(request.namespace) ?? new Set<string>();
    usedByNamespace.set(request.namespace, used);
    const base = request.preferred ?? preferredPrismaName(request.source);
    let candidate = base;
    let suffix = 2;
    let attempts = 0;
    while (
      used.has(candidate) ||
      !isPrismaIdentifier(candidate) ||
      isReservedPrismaName(candidate)
    ) {
      attempts += 1;
      if (attempts > maxAttempts) {
        return { ok: false, names, mappings };
      }
      candidate = `${base}_${suffix}`;
      suffix += 1;
    }
    used.add(candidate);
    names.set(request.key, candidate);
    mappings.push({
      kind: request.kind,
      namespace: request.namespace,
      source: request.source,
      generated: candidate,
    });
  }

  return { ok: true, names, mappings };
}

/**
 * Build the export manifest recorded beside a generated schema.
 */
export function buildPrismaManifest(
  mappings: PrismaIdentifierMapping[],
): {
  contractVersion: string;
  mappings: PrismaIdentifierMapping[];
} {
  return {
    contractVersion: PRISMA_IDENTIFIER_CONTRACT_VERSION,
    mappings,
  };
}
