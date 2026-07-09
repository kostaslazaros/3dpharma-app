/**
 * Drug data types and API integration for the compatibility checker
 * This module ONLY uses the FastAPI backend - NO mock/hardcoded data
 */

import * as api from './api';

// =============================================================================
// Types
// =============================================================================

export interface Drug {
  id: string;
  name: string;
  type: 'small molecule' | 'biotech' | 'unknown';
  groups: string[];
  description: string;
  categories: string[];
  dosing: {
    frequency: string | null;
    timesPerDay: number | null;
    routes: string[];
    strengths: string[];
    forms: string[];
  };
  foodInteractions: string[];
  interactions: DrugInteraction[];
  properties: {
    meltingPoint?: string;
    waterSolubility?: string;
    molecularWeight?: string;
    logP?: string;
    pKa?: string;
  };
  pharmacokinetics: {
    halfLife?: string;
    absorption?: string;
    metabolism?: string;
  };
}

export interface DrugInteraction {
  drugName: string;
  drugId: string;
  description: string;
  severity: 'severe' | 'moderate' | 'minor';
}

export interface CompatibilityResult {
  drug1: string;
  drug2: string;
  compatible: boolean;
  issues: string[];
  warnings: string[];
  recommendations: string[];
  interactions: DrugInteraction[];
  routes: {
    drug1: string[];
    drug2: string[];
    common: string[];
  };
  dosing: {
    drug1: { frequency: string | null; timesPerDay: number | null };
    drug2: { frequency: string | null; timesPerDay: number | null };
  };
}

export interface MultiDrugCompatibilityResult {
  drugs: string[];
  compatible: boolean;
  issues: string[];
  warnings: string[];
  recommendations: string[];
  interactions: Array<{
    drug1: string;
    drug2: string;
    interaction: DrugInteraction;
  }>;
  /** Pairs with no interaction (for 3+ drugs), e.g. [["DrugA", "DrugB"], ...] */
  noInteractionPairs: Array<[string, string]>;
  drugDetails: Array<{
    name: string;
    routes: string[];
    frequency: string | null;
    timesPerDay: number | null;
  }>;
  commonRoutes: string[];
}

// =============================================================================
// API Status
// =============================================================================

let apiAvailable = false;
let apiCheckPromise: Promise<boolean> | null = null;
let lastApiError: string | null = null;

async function checkApiAvailability(): Promise<boolean> {
  try {
    await api.healthCheck();
    apiAvailable = true;
    lastApiError = null;
    console.log('✅ API connected successfully - using real database (17,430 drugs)');
    return true;
  } catch (error) {
    apiAvailable = false;
    lastApiError = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ API not available:', lastApiError);
    console.error('Please ensure the FastAPI backend is running on http://localhost:8000');
    return false;
  }
}

// Ensure we wait for API check before using
async function ensureApiChecked(): Promise<boolean> {
  if (apiCheckPromise === null) {
    apiCheckPromise = checkApiAvailability();
  }
  return apiCheckPromise;
}

// Check on load
apiCheckPromise = checkApiAvailability();

// Export API status for components to check
export function isApiAvailable(): boolean {
  return apiAvailable;
}

export function getApiError(): string | null {
  return lastApiError;
}

export async function waitForApiCheck(): Promise<boolean> {
  return ensureApiChecked();
}

// =============================================================================
// Helper Functions
// =============================================================================

function convertApiDrugToLocal(apiDrug: api.DrugSummary): Drug {
  return {
    id: apiDrug.drugbank_id || '',
    name: apiDrug.name,
    type: (apiDrug.type as Drug['type']) || 'unknown',
    groups: apiDrug.groups,
    description: apiDrug.description,
    categories: apiDrug.categories,
    dosing: {
      frequency: apiDrug.dosing.frequency,
      timesPerDay: apiDrug.dosing.times_per_day ? parseInt(apiDrug.dosing.times_per_day) : null,
      routes: apiDrug.dosing.routes,
      strengths: apiDrug.dosing.strengths || [],
      forms: apiDrug.dosing.forms || [],
    },
    foodInteractions: apiDrug.food_interactions || [],
    interactions: apiDrug.interactions_list.map((i) => ({
      drugName: i.name,
      drugId: i.drugbank_id || '',
      description: i.description,
      severity: 'moderate' as const,
    })),
    properties: {
      meltingPoint: apiDrug.properties['Melting Point'],
      waterSolubility: apiDrug.properties['Water Solubility'],
      molecularWeight: apiDrug.properties['Molecular Weight'],
      logP: apiDrug.properties['logP'],
      pKa: apiDrug.properties['pKa'],
    },
    pharmacokinetics: {
      halfLife: apiDrug.pharmacokinetics.half_life || undefined,
      absorption: apiDrug.pharmacokinetics.absorption || undefined,
      metabolism: apiDrug.pharmacokinetics.metabolism || undefined,
    },
  };
}

function convertApiCompatibilityToLocal(apiResult: api.CompatibilityResult): CompatibilityResult {
  return {
    drug1: apiResult.drug1,
    drug2: apiResult.drug2,
    compatible: apiResult.compatible,
    issues: apiResult.issues,
    warnings: apiResult.warnings,
    recommendations: apiResult.recommendations,
    interactions: apiResult.interactions.map((i) => ({
      drugName: i.drug,
      drugId: '',
      description: i.description,
      severity: i.severity as DrugInteraction['severity'],
    })),
    routes: apiResult.routes,
    dosing: {
      drug1: {
        frequency: apiResult.dosing.drug1.frequency,
        timesPerDay: apiResult.dosing.drug1.times_per_day
          ? parseInt(apiResult.dosing.drug1.times_per_day)
          : null,
      },
      drug2: {
        frequency: apiResult.dosing.drug2.frequency,
        timesPerDay: apiResult.dosing.drug2.times_per_day
          ? parseInt(apiResult.dosing.drug2.times_per_day)
          : null,
      },
    },
  };
}

// =============================================================================
// Exported Functions (API ONLY - no mock data)
// =============================================================================

/**
 * Search drugs - REQUIRES API
 */
export async function searchDrugsAsync(query: string): Promise<Drug[]> {
  if (!query || query.length < 2) return [];

  await ensureApiChecked();

  if (!apiAvailable) {
    console.error('Cannot search: API not available');
    throw new Error('Backend API not available. Please ensure the FastAPI server is running.');
  }

  const results = await api.searchDrugs(query);
  return results.map((r) => ({
    id: r.drugbank_id || '',
    name: r.name,
    type: (r.type as Drug['type']) || 'unknown',
    groups: [],
    description: '',
    categories: r.categories,
    dosing: { frequency: null, timesPerDay: null, routes: [] },
    interactions: [],
    properties: {},
    pharmacokinetics: {},
  }));
}

/**
 * Synchronous search - NOT AVAILABLE (returns empty, use async version)
 */
export function searchDrugs(query: string): Drug[] {
  console.warn('searchDrugs (sync) is deprecated. Use searchDrugsAsync instead.');
  return [];
}

/**
 * Find drug by name - REQUIRES API
 */
export async function findDrugAsync(name: string): Promise<Drug | undefined> {
  await ensureApiChecked();

  if (!apiAvailable) {
    console.error('Cannot find drug: API not available');
    throw new Error('Backend API not available. Please ensure the FastAPI server is running.');
  }

  try {
    const drugInfo = await api.getDrugInfo(name);
    return convertApiDrugToLocal(drugInfo);
  } catch (error) {
    console.warn('Drug not found:', name);
    return undefined;
  }
}

/**
 * Synchronous find - NOT AVAILABLE (returns undefined, use async version)
 */
export function findDrug(name: string): Drug | undefined {
  console.warn('findDrug (sync) is deprecated. Use findDrugAsync instead.');
  return undefined;
}

/**
 * Get drugs by category - REQUIRES API
 */
export async function getDrugsByCategoryAsync(category: string): Promise<Drug[]> {
  await ensureApiChecked();

  if (!apiAvailable) {
    console.error('Cannot get drugs by category: API not available');
    throw new Error('Backend API not available. Please ensure the FastAPI server is running.');
  }

  // Search by category name
  const results = await api.searchDrugs(category);
  return results.map((r) => ({
    id: r.drugbank_id || '',
    name: r.name,
    type: (r.type as Drug['type']) || 'unknown',
    groups: [],
    description: '',
    categories: r.categories,
    dosing: { frequency: null, timesPerDay: null, routes: [] },
    interactions: [],
    properties: {},
    pharmacokinetics: {},
  }));
}

/**
 * Synchronous category lookup - NOT AVAILABLE (returns empty, use async version)
 */
export function getDrugsByCategory(category: string): Drug[] {
  console.warn('getDrugsByCategory (sync) is deprecated. Use getDrugsByCategoryAsync instead.');
  return [];
}

/**
 * Get all drugs - NOT AVAILABLE (database too large, use search)
 */
export function getAllDrugs(): Drug[] {
  console.warn('getAllDrugs is not available. Use searchDrugsAsync to search the database.');
  return [];
}

/**
 * Check compatibility - REQUIRES API
 */
export async function checkCompatibilityAsync(
  drug1Name: string,
  drug2Name: string
): Promise<CompatibilityResult> {
  await ensureApiChecked();

  if (!apiAvailable) {
    console.error('Cannot check compatibility: API not available');
    throw new Error('Backend API not available. Please ensure the FastAPI server is running.');
  }

  const result = await api.checkCompatibility(drug1Name, drug2Name);
  return convertApiCompatibilityToLocal(result);
}

/**
 * Synchronous compatibility check - NOT AVAILABLE (use async version)
 */
export function checkCompatibility(drug1Name: string, drug2Name: string): CompatibilityResult {
  console.warn('checkCompatibility (sync) is deprecated. Use checkCompatibilityAsync instead.');
  return {
    drug1: drug1Name,
    drug2: drug2Name,
    compatible: false,
    issues: ['Backend API not available. Please use the async version.'],
    warnings: [],
    recommendations: [],
    interactions: [],
    routes: { drug1: [], drug2: [], common: [] },
    dosing: {
      drug1: { frequency: null, timesPerDay: null },
      drug2: { frequency: null, timesPerDay: null },
    },
  };
}

/**
 * Check multi-drug compatibility - REQUIRES API
 */
export async function checkMultiDrugCompatibilityAsync(
  drugNames: string[]
): Promise<MultiDrugCompatibilityResult> {
  await ensureApiChecked();

  if (!apiAvailable) {
    console.error('Cannot check multi-drug compatibility: API not available');
    throw new Error('Backend API not available. Please ensure the FastAPI server is running.');
  }

  const result = await api.checkMultiDrugCompatibility(drugNames);
  return {
    drugs: result.drugs,
    compatible: result.compatible,
    issues: result.issues,
    warnings: result.warnings,
    recommendations: result.recommendations,
    interactions: result.interactions.map((i) => ({
      drug1: i.drug1,
      drug2: i.drug2,
      interaction: {
        drugName: i.interaction.drug,
        drugId: '',
        description: i.interaction.description,
        severity: i.interaction.severity as DrugInteraction['severity'],
      },
    })),
    drugDetails: result.drug_details.map((d) => ({
      name: d.name,
      routes: d.routes,
      frequency: d.frequency,
      timesPerDay: d.times_per_day ? parseInt(d.times_per_day) : null,
    })),
    commonRoutes: result.common_routes,
  };
}

/**
 * Synchronous multi-drug check - NOT AVAILABLE (use async version)
 */
export function checkMultiDrugCompatibility(drugNames: string[]): MultiDrugCompatibilityResult {
  console.warn('checkMultiDrugCompatibility (sync) is deprecated. Use checkMultiDrugCompatibilityAsync instead.');
  return {
    drugs: drugNames,
    compatible: false,
    issues: ['Backend API not available. Please use the async version.'],
    warnings: [],
    recommendations: [],
    interactions: [],
    drugDetails: [],
    commonRoutes: [],
  };
}

/**
 * Get drug summary - NOT AVAILABLE synchronously (use async version)
 */
export function getDrugSummary(drugName: string) {
  console.warn('getDrugSummary (sync) is deprecated. Use getDrugSummaryAsync instead.');
  return null;
}

/**
 * Get drug summary async - REQUIRES API
 */
export async function getDrugSummaryAsync(drugName: string) {
  await ensureApiChecked();

  if (!apiAvailable) {
    console.error('Cannot get drug summary: API not available');
    throw new Error('Backend API not available. Please ensure the FastAPI server is running.');
  }

  try {
    const drugInfo = await api.getDrugInfo(drugName);
    const drug = convertApiDrugToLocal(drugInfo);
    return {
      name: drug.name,
      id: drug.id,
      type: drug.type,
      groups: drug.groups,
      description: drug.description,
      categories: drug.categories,
      dosing: drug.dosing,
      foodInteractions: drug.foodInteractions,
      interactionCount: drug.interactions.length,
      interactions: drug.interactions,
      properties: drug.properties,
      pharmacokinetics: drug.pharmacokinetics,
    };
  } catch (error) {
    console.warn('Drug not found:', drugName);
    return null;
  }
}

// Drug categories - these should come from API in production
// Keeping minimal list for UI purposes only
export const drugCategories = [
  'NSAIDs',
  'ACE Inhibitors',
  'ARB',
  'Statins',
  'Antidiabetic',
  'Anticoagulant',
  'Antiarrhythmic',
  'Antihypertensive',
  'Analgesic',
  'Anti-inflammatory',
  'Cardiovascular',
];
