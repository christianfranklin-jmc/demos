/**
 * Faux data products for sidebar navigation.
 * ROMI is the active/demo product. Others show various lifecycle states.
 */

import type { StepNumber, StepStatus } from "../../lib/types";

export interface DataProduct {
  id: string;
  name: string;
  owner: string;
  currentStep: StepNumber;
  overallStatus: "active" | "awaiting" | "complete" | "new";
  stepStatuses: Record<StepNumber, StepStatus>;
}

export const DATA_PRODUCTS: DataProduct[] = [
  {
    id: "dp-romi-001",
    name: "New Data Product",
    owner: "Jennifer Moss",
    currentStep: 1,
    overallStatus: "active",
    stepStatuses: { 0: "skipped", 1: "in_progress", 2: "not_started", 3: "not_started", 4: "not_started" },
  },
  {
    id: "dp-churn-002",
    name: "Customer Churn",
    owner: "David Park",
    currentStep: 3,
    overallStatus: "active",
    stepStatuses: { 0: "skipped", 1: "approved", 2: "approved", 3: "in_progress", 4: "not_started" },
  },
  {
    id: "dp-rev-003",
    name: "Revenue Attribution",
    owner: "Sarah Chen",
    currentStep: 2,
    overallStatus: "awaiting",
    stepStatuses: { 0: "skipped", 1: "approved", 2: "awaiting_approval", 3: "not_started", 4: "not_started" },
  },
  {
    id: "dp-cltv-004",
    name: "Customer Lifetime Value",
    owner: "Marcus Webb",
    currentStep: 4,
    overallStatus: "complete",
    stepStatuses: { 0: "skipped", 1: "approved", 2: "approved", 3: "approved", 4: "approved" },
  },
  {
    id: "dp-pipe-005",
    name: "Sales Pipeline Health",
    owner: "Anya Patel",
    currentStep: 1,
    overallStatus: "new",
    stepStatuses: { 0: "skipped", 1: "not_started", 2: "not_started", 3: "not_started", 4: "not_started" },
  },
];

export function getDataProduct(id: string): DataProduct | undefined {
  return DATA_PRODUCTS.find((dp) => dp.id === id);
}
