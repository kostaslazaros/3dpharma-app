/**
 * API client for the FastAPI backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://threedpharma-backend.onrender.com';

/**
 * Generic fetch wrapper with error handling
 */
async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const defaultHeaders: HeadersInit = {
    'Content-Type': 'application/json',
  };

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(errorData.detail || `API Error: ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// API Types
// =============================================================================

export interface DrugSearchResult {
  name: string;
  drugbank_id: string | null;
  type: string | null;
  categories: string[];
}

export interface DosingInfo {
  has_dosing: boolean;
  source: string | null;
  frequency: string | null;
  times_per_day: string | null;
  routes: string[];
}

export interface Pharmacokinetics {
  half_life: string | null;
  absorption: string | null;
  metabolism: string | null;
}

export interface DrugSummary {
  name: string;
  drugbank_id: string | null;
  type: string | null;
  groups: string[];
  description: string;
  categories: string[];
  dosing: DosingInfo;
  interaction_count: number;
  food_interactions: string[];
  interactions_list: Array<{
    drugbank_id?: string;
    name: string;
    description: string;
  }>;
  properties: Record<string, string>;
  pharmacokinetics: Pharmacokinetics;
  dosages: Array<{
    form?: string;
    route?: string;
    strength?: string;
  }>;
}

export interface InteractionDetail {
  drug: string;
  description: string;
  severity: string;
  source?: string;
}

export interface CompatibilityResult {
  drug1: string;
  drug2: string;
  compatible: boolean;
  issues: string[];
  warnings: string[];
  recommendations: string[];
  drug1_data: DrugSummary | null;
  drug2_data: DrugSummary | null;
  interactions: InteractionDetail[];
  routes: {
    drug1: string[];
    drug2: string[];
    common: string[];
  };
  dosing: {
    drug1: { frequency: string | null; times_per_day: string | null };
    drug2: { frequency: string | null; times_per_day: string | null };
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
    interaction: InteractionDetail;
  }>;
  no_interaction_pairs?: Array<[string, string]>;
  drug_details: Array<{
    name: string;
    type: string | null;
    routes: string[];
    frequency: string | null;
    times_per_day: string | null;
  }>;
  common_routes: string[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  response: string;
  sources: string[];
  drugs_mentioned: string[];
}

export interface DatabaseInfo {
  total_drugs: number;
  drugs_with_dosing: number;
  source: string;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Search for drugs by name
 */
export async function searchDrugs(query: string): Promise<DrugSearchResult[]> {
  if (query.length < 2) return [];
  return fetchApi<DrugSearchResult[]>(`/drugs/search?q=${encodeURIComponent(query)}`);
}

/**
 * Get detailed drug information
 */
export async function getDrugInfo(drugName: string): Promise<DrugSummary> {
  return fetchApi<DrugSummary>(`/drugs/info/${encodeURIComponent(drugName)}`);
}

/**
 * Get all drug categories
 */
export async function getCategories(): Promise<string[]> {
  return fetchApi<string[]>('/drugs/categories');
}

/**
 * Get drugs by category
 */
export async function getDrugsByCategory(category: string): Promise<string[]> {
  return fetchApi<string[]>(`/drugs/categories/${encodeURIComponent(category)}`);
}

/**
 * Get alternative drugs
 */
export async function getAlternatives(drugName: string): Promise<{
  drug: string;
  alternatives: string[];
  count: number;
}> {
  return fetchApi(`/drugs/alternatives/${encodeURIComponent(drugName)}`);
}

/**
 * Get database info
 */
export async function getDatabaseInfo(): Promise<DatabaseInfo> {
  return fetchApi<DatabaseInfo>('/drugs/database/info');
}

/**
 * Check compatibility between two drugs
 */
export async function checkCompatibility(
  drug1: string,
  drug2: string
): Promise<CompatibilityResult> {
  return fetchApi<CompatibilityResult>('/compatibility/check', {
    method: 'POST',
    body: JSON.stringify({ drug1, drug2 }),
  });
}

/**
 * Check compatibility between multiple drugs
 */
export async function checkMultiDrugCompatibility(
  drugs: string[]
): Promise<MultiDrugCompatibilityResult> {
  return fetchApi<MultiDrugCompatibilityResult>('/compatibility/check-multi', {
    method: 'POST',
    body: JSON.stringify({ drugs }),
  });
}

/**
 * Send a message to the AI chat
 */
export async function sendChatMessage(
  message: string,
  history: ChatMessage[] = []
): Promise<ChatResponse> {
  return fetchApi<ChatResponse>('/chat/message', {
    method: 'POST',
    body: JSON.stringify({ message, history }),
  });
}

/**
 * Check AI chat availability
 */
export async function getChatStatus(): Promise<{
  available: boolean;
  message: string;
}> {
  return fetchApi('/chat/status');
}

/**
 * Get AI-generated drug synopsis
 */
export async function getDrugSynopsis(drugName: string): Promise<{
  drug_name: string;
  synopsis: string;
  sources: string[];
}> {
  return fetchApi(`/chat/synopsis/${encodeURIComponent(drugName)}`);
}

/**
 * Health check
 */
export async function healthCheck(): Promise<{
  status: string;
  database: {
    loaded: boolean;
    total_drugs: number;
    drugs_with_dosing: number;
  };
}> {
  return fetchApi('/health');
}

/**
 * Find compatible alternatives from a category that have no interactions with a target drug
 */
export interface CompatibleAlternative {
  name: string;
  type: string | null;
  has_dosing: boolean;
  frequency: string | null;
  routes: string[];
}

export async function findCompatibleAlternatives(
  targetDrug: string,
  category: string,
  limit: number = 10
): Promise<{
  target_drug: string;
  category: string;
  alternatives: CompatibleAlternative[];
  count: number;
}> {
  return fetchApi('/compatibility/find-alternatives', {
    method: 'POST',
    body: JSON.stringify({
      target_drug: targetDrug,
      category: category,
      limit: limit
    }),
  });
}

// =============================================================================
// Co-administration (clinical) API
// =============================================================================

export interface PatientContext {
  sex?: string | null;
  age?: number | null;
  conditions: string[];
  diseases: string[];
}

export interface CoAdminHit {
  drugs: string[];
  condition?: string | null;
  condition_label?: string | null;
  description: string;
  severity: string;           // severe | moderate | minor | unknown
  emoji?: string | null;
  source?: string | null;
  category: string;           // contraindication | interaction | adverse_effect
}

export interface CoAdminResult {
  drugs: string[];
  resolved_drugs: string[];
  unresolved_drugs: string[];
  patient: PatientContext;
  contraindications: CoAdminHit[];
  interactions: CoAdminHit[];
  adverse_effects: CoAdminHit[];
  summary: string;
  disclaimer: string;
}

export interface ConditionOption {
  key: string;
  label: string;
}

/**
 * List supported patient conditions for the co-administration checker.
 */
export async function getCoAdminConditions(): Promise<ConditionOption[]> {
  const data = await fetchApi<{ conditions: ConditionOption[] }>('/coadministration/conditions');
  return data.conditions;
}

/**
 * Run a clinical co-administration check.
 */
export async function checkCoAdministration(
  drugs: string[],
  patient: PatientContext
): Promise<CoAdminResult> {
  return fetchApi<CoAdminResult>('/coadministration/check', {
    method: 'POST',
    body: JSON.stringify({ drugs, patient }),
  });
}

/**
 * Ask the clinical co-administration AI assistant (tool-using, grounded).
 */
export async function sendCoAdminChat(
  message: string,
  history: ChatMessage[] = []
): Promise<ChatResponse> {
  return fetchApi<ChatResponse>('/chat/coadmin', {
    method: 'POST',
    body: JSON.stringify({ message, history }),
  });
}

/**
 * Check clinical AI assistant availability.
 */
export async function getCoAdminStatus(): Promise<{
  available: boolean;
  provider: string;
  model: string;
  message: string;
}> {
  return fetchApi('/chat/coadmin/status');
}