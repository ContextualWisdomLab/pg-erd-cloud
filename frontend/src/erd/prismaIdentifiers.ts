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

export type PrismaIdentifierFailure = {
  key: string;
  kind: PrismaIdentifierKind;
  namespace: string;
  source: string;
  preferred: string;
  lastCandidate: string;
  attempts: number;
  maxAttempts: number;
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
  failure?: PrismaIdentifierFailure;
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
  const sourceOrder = compareUnicode(left.source, right.source);
  if (sourceOrder !== 0) {
    return sourceOrder;
  }
  const namespaceOrder = compareUnicode(left.namespace, right.namespace);
  if (namespaceOrder !== 0) {
    return namespaceOrder;
  }
  return compareUnicode(left.key, right.key);
}

function compareUnicode(left: string, right: string): number {
  let leftIndex = 0;
  let rightIndex = 0;
  while (leftIndex < left.length && rightIndex < right.length) {
    const leftCodePoint = left.codePointAt(leftIndex) ?? 0;
    const rightCodePoint = right.codePointAt(rightIndex) ?? 0;
    if (leftCodePoint !== rightCodePoint) {
      return leftCodePoint < rightCodePoint ? -1 : 1;
    }
    leftIndex += leftCodePoint > 0xffff ? 2 : 1;
    rightIndex += rightCodePoint > 0xffff ? 2 : 1;
  }
  if (leftIndex === left.length && rightIndex === right.length) {
    return 0;
  }
  return leftIndex === left.length ? -1 : 1;
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
        return {
          ok: false,
          names,
          mappings,
          failure: {
            key: request.key,
            kind: request.kind,
            namespace: request.namespace,
            source: request.source,
            preferred: base,
            lastCandidate: candidate,
            attempts,
            maxAttempts,
          },
        };
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
  failure?: PrismaIdentifierFailure,
): {
  contractVersion: string;
  mappings: PrismaIdentifierMapping[];
  failure?: PrismaIdentifierFailure;
} {
  const manifest = {
    contractVersion: PRISMA_IDENTIFIER_CONTRACT_VERSION,
    mappings,
  };
  return failure ? { ...manifest, failure } : manifest;
}
