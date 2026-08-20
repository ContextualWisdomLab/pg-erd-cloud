/**
 * Pinned Prisma identifier contract used by canvas export.
 *
 * Grammar and reserved names are taken from the Prisma Schema API and the
 * prisma-engines reserved-model-name table. Keep this file aligned with
 * `backend/app/spec/prisma_identifiers.py`.
 */

/** Prisma Schema API model/field identifier grammar. */
export const PRISMA_IDENTIFIER_PATTERN = /^[A-Za-z][A-Za-z0-9_]*$/;

/** Contract version recorded on every export manifest. */
export const PRISMA_IDENTIFIER_CONTRACT_VERSION = "2026-08-16.prisma-6-reserved";

/**
 * Maximum unique-suffix attempts per identifier. Exceeding this fails closed
 * instead of emitting an ambiguous or truncated name.
 */
export const PRISMA_IDENTIFIER_MAX_ATTEMPTS = 10_000;

/**
 * Schema-block keywords. Compared case-insensitively because
 * `model model {` is unparseable and buyers also collide `Model` / `MODEL`.
 */
export const PRISMA_SCHEMA_KEYWORDS = [
  "datasource",
  "enum",
  "generator",
  "model",
  "type",
  "view",
] as const;

/** Scalar type names that cannot be reused as model or enum names. */
export const PRISMA_SCALAR_TYPE_NAMES = [
  "BigInt",
  "Boolean",
  "Bytes",
  "DateTime",
  "Decimal",
  "Float",
  "Int",
  "Json",
  "String",
  "Unsupported",
] as const;

/**
 * Prisma Client reserved model names from prisma-engines
 * `psl/parser-database/src/names/reserved_model_names.rs` (main, 2026-08-16).
 * Compared case-sensitively, matching the engine table.
 */
export const PRISMA_CLIENT_RESERVED_NAMES = [
  "PrismaClient",
  "async",
  "await",
  "break",
  "case",
  "catch",
  "class",
  "const",
  "continue",
  "debugger",
  "default",
  "delete",
  "do",
  "else",
  "enum",
  "export",
  "extends",
  "false",
  "finally",
  "for",
  "function",
  "if",
  "implements",
  "import",
  "in",
  "instanceof",
  "interface",
  "let",
  "new",
  "null",
  "package",
  "private",
  "protected",
  "public",
  "return",
  "super",
  "switch",
  "this",
  "throw",
  "true",
  "try",
  "typeof",
  "using",
  "var",
  "void",
  "while",
  "with",
  "yield",
] as const;

const SCHEMA_KEYWORD_SET = new Set(
  PRISMA_SCHEMA_KEYWORDS.map((name) => name.toLowerCase()),
);
const SCALAR_TYPE_SET = new Set<string>(PRISMA_SCALAR_TYPE_NAMES);
const CLIENT_RESERVED_SET = new Set<string>(PRISMA_CLIENT_RESERVED_NAMES);

/**
 * Return whether `name` is reserved for a Prisma model, enum, or type.
 */
export function isReservedPrismaName(name: string): boolean {
  return (
    SCHEMA_KEYWORD_SET.has(name.toLowerCase()) ||
    SCALAR_TYPE_SET.has(name) ||
    CLIENT_RESERVED_SET.has(name)
  );
}

/**
 * Return whether `name` matches the Prisma identifier grammar.
 */
export function isPrismaIdentifier(name: string): boolean {
  return PRISMA_IDENTIFIER_PATTERN.test(name);
}
