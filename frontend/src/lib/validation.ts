/**
 * Standards validation engine.
 * Validates field values against standards rules and produces QualityFlag objects.
 */

import type { StepNumber, QualityFlag, FlagType } from "./types";
import { STANDARDS, type Standard } from "../data/standards";

/**
 * Validate a single field against applicable standards.
 * Returns an array of violations (as QualityFlags).
 */
export function validateField(
  step: StepNumber,
  fieldKey: string,
  value: any,
  dataProductId: string
): QualityFlag[] {
  const applicable = STANDARDS.filter(
    (s) => s.step === step && s.fieldKey === fieldKey && s.validate
  );

  const violations: QualityFlag[] = [];
  for (const standard of applicable) {
    if (!standard.validate!(value)) {
      violations.push({
        flag_id: `std-${standard.id}-${Date.now()}`,
        data_product_id: dataProductId,
        step,
        flag_type: standard.flagType as FlagType,
        description: `${standard.rule}: ${standard.description}`,
        status: "open",
        resolution: null,
        resolved_by: null,
        resolved_at: null,
        created_at: new Date().toISOString(),
      });
    }
  }
  return violations;
}

/**
 * Validate all fields in an artifact against standards.
 * Returns pass/fail status per standard.
 */
export function validateStandards(
  step: StepNumber,
  artifact: any
): { standard: Standard; passes: boolean }[] {
  const stepStandards = STANDARDS.filter((s) => s.step === step);
  return stepStandards.map((standard) => {
    if (!standard.validate || !standard.fieldKey) {
      return { standard, passes: true }; // no validator = passes by default
    }
    const value = artifact?.[standard.fieldKey] ?? null;
    return { standard, passes: standard.validate(value) };
  });
}

/**
 * Check if a standards flag already exists for a given standard+field combo.
 */
export function hasExistingFlag(
  existingFlags: QualityFlag[],
  step: StepNumber,
  flagType: FlagType
): boolean {
  return existingFlags.some(
    (f) => f.step === step && f.flag_type === flagType && f.status === "open"
  );
}
