/**
 * Normalizes a newly introduced optional API metric without inventing data.
 * Missing and explicit null both mean "unavailable". Any present non-number
 * remains a contract error so schema regressions are visible during testing.
 */
export function normalizeOptionalNullableNumber(value: unknown, field: string): number | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`Invalid API field ${field}: expected a finite number or null.`);
  }
  return value;
}
