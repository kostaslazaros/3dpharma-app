"""
Drug Compatibility Checker - Streamlit App
3D Printing Compatibility Assessment Tool
"""

import streamlit as st
import json
import os
import re
import time
import importlib
from typing import Dict, List, Optional

import ijson
import openai
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup


if 'active_app' not in st.session_state:
    st.session_state['active_app'] = 'drug'


def _rerun_app():
    """Compatibility wrapper for Streamlit rerun APIs."""
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        st.rerun()


def render_athero_app():
    """Embed the Athero app inside this Streamlit session."""
    os.environ["ATHERO_EMBEDDED"] = "1"
    if 'athero_module' not in st.session_state:
        try:
            st.session_state['athero_module'] = importlib.import_module("athero.athero.app")
        except ModuleNotFoundError:
            st.error("Unable to load the Athero app module. Ensure 'athero/athero/app.py' exists.")
            return
    athero_app = st.session_state['athero_module']
    # Ensure required session_state keys exist before delegating to the Athero app.
    if 'data_loaded' not in st.session_state:
        st.session_state['data_loaded'] = False
    if 'all_data' not in st.session_state:
        st.session_state['all_data'] = []
    if 'yearly_counts' not in st.session_state:
        st.session_state['yearly_counts'] = {}
    if 'categories' not in st.session_state:
        st.session_state['categories'] = []
    if hasattr(athero_app, "main"):
        athero_app.main()
    else:
        st.error("The Athero app module does not expose a 'main()' function.")


class ComprehensiveDrugQuery:
    """Query interface for comprehensive database with OpenFDA fallback"""

    def __init__(
        self,
        db_file: str = 'comprehensive_drug_database_compact.json',
        openfda_file: str = 'OpenFDAfull.json',
    ):
        # Resolve database path (use compact version if available)
        preferred_db = os.getenv('DRUG_DB_FILE', db_file)
        if not os.path.exists(preferred_db):
            preferred_db = 'comprehensive_drug_database.json'
        
        if not os.path.exists(preferred_db):
            raise FileNotFoundError(
                f"Database file not found. Expected one of: {db_file} or comprehensive_drug_database.json. "
                f"Please ensure the database file is available in the working directory."
            )
        
        self.db_file = preferred_db
        print(f"Loading drug database from {self.db_file}")
        with open(self.db_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.metadata = data.get('metadata', {})
        self.drugs = data.get('drugs', [])
        
        # Allow disabling heavy OpenFDA dataset to stay within low-memory plans
        openfda_enabled = os.getenv('ENABLE_OPENFDA_DATA', 'true').lower() not in ('0', 'false', 'no')
        self.openfda_drugs = {}
        self.openfda_name_index = {}
        if openfda_enabled:
            self._load_openfda_data(openfda_file)
        
        # Create name index
        self.name_index = {}
        self.id_index = {}
        
        for i, drug in enumerate(self.drugs):
            name = drug.get('name', '').lower()
            if name:
                self.name_index[name] = i
            
            drug_id = drug.get('drugbank_ids', {}).get('primary')
            if drug_id:
                self.id_index[drug_id] = i
    
    def search_drugs(self, query: str) -> List[str]:
        """Search drugs by partial name match"""
        query_lower = query.lower()
        results = []
        for name in self.name_index.keys():
            if query_lower in name:
                # Get the original case name
                idx = self.name_index[name]
                results.append(self.drugs[idx].get('name'))
        return sorted(results)[:50]  # Limit to 50 results
    
    def _load_openfda_data(self, openfda_file: str) -> None:
        """Stream OpenFDA dataset and keep only lightweight dosing/index info."""
        try:
            with open(openfda_file, 'rb') as f:
                for drug_id, raw_entry in ijson.kvitems(f, 'drugs'):
                    simplified = self._simplify_openfda_entry(raw_entry)
                    if simplified:
                        self.openfda_drugs[drug_id] = simplified
                        self._index_openfda_name(simplified.get('drug_name'), drug_id)
                        for name in simplified.get('generic_names', []):
                            self._index_openfda_name(name, drug_id)
                        for name in simplified.get('brand_names', []):
                            self._index_openfda_name(name, drug_id)
        except FileNotFoundError:
            self.openfda_drugs = {}
            self.openfda_name_index = {}
        except Exception as exc:
            # If streaming fails, log minimal information and continue without OpenFDA
            print(f"Warning: Failed to load OpenFDA data: {exc}")
            self.openfda_drugs = {}
            self.openfda_name_index = {}
    
    def _simplify_openfda_entry(self, raw_entry: Dict) -> Optional[Dict]:
        """Reduce OpenFDA entry to essential fields to stay within memory limits."""
        if not raw_entry:
            return None
        openfda_data = raw_entry.get('openfda_data', {})
        parsed_dosing = openfda_data.get('parsed_dosing', {}) or {}
        openfda_meta = openfda_data.get('openfda', {}) or {}
        
        def _as_list(values):
            if isinstance(values, list):
                return values
            if isinstance(values, str):
                return [values]
            return []
        
        def _clean_list(values):
            return [str(v).strip() for v in _as_list(values) if isinstance(v, str) and v.strip()]
        
        simplified = {
            'drug_name': raw_entry.get('drug_name', '').strip(),
            'generic_names': _clean_list(openfda_meta.get('generic_name', [])),
            'brand_names': _clean_list(openfda_meta.get('brand_name', [])),
            'parsed_dosing': {
                'frequency': parsed_dosing.get('frequency'),
                'times_per_day': parsed_dosing.get('times_per_day'),
                'times_per_day_range': parsed_dosing.get('times_per_day_range'),
                'routes': parsed_dosing.get('routes') or _clean_list(openfda_meta.get('route', [])),
                'route': parsed_dosing.get('route'),
                'instructions': parsed_dosing.get('instructions'),
                'has_dosing': parsed_dosing.get('has_dosing'),
                'source': parsed_dosing.get('source'),
            }
        }
        # Drop entries without useful dosing data
        if not any(simplified['parsed_dosing'].values()):
            return None
        return simplified
    
    def _index_openfda_name(self, name: Optional[str], drug_id: str) -> None:
        if not name:
            return
        key = name.lower().strip()
        if not key:
            return
        self.openfda_name_index.setdefault(key, drug_id)
    
    def _search_openfda_partial(self, query_lower: str) -> Optional[Dict]:
        for entry in self.openfda_drugs.values():
            stored = entry.get('drug_name', '').lower()
            if query_lower in stored or stored.startswith(query_lower):
                return entry
        return None
    
    def _get_openfda_dosing(self, drug_name: str) -> Optional[Dict]:
        if not self.openfda_drugs:
            return None
        query_lower = drug_name.lower().strip()
        entry_id = self.openfda_name_index.get(query_lower)
        entry = self.openfda_drugs.get(entry_id) if entry_id else None
        if not entry:
            entry = self._search_openfda_partial(query_lower)
        if not entry:
            return None
        return entry.get('parsed_dosing', {})
    
    @staticmethod
    def _normalize_category_name(category_entry) -> str:
        """Normalize category entries that may be dicts or strings."""
        if isinstance(category_entry, dict):
            for key in ('category', 'name', 'mesh_id'):
                value = category_entry.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        elif isinstance(category_entry, str):
            return category_entry.strip()
        elif category_entry is not None:
            text = str(category_entry).strip()
            if text:
                return text
        return ''
    
    def get_all_categories(self) -> List[str]:
        """Get all unique drug categories"""
        categories = set()
        for drug in self.drugs:
            for cat in drug.get('categories', []):
                cat_name = self._normalize_category_name(cat)
                if cat_name:
                    categories.add(cat_name)
        return sorted(list(categories))
    
    def get_drugs_by_category(self, category: str) -> List[str]:
        """Get all drugs in a specific category"""
        results = []
        category_lower = category.lower()
        for drug in self.drugs:
            for cat in drug.get('categories', []):
                cat_name = self._normalize_category_name(cat).lower()
                if not cat_name:
                    continue
                if category_lower in cat_name or cat_name in category_lower:
                    results.append(drug.get('name'))
                    break
        return sorted(list(set(results)))  # Remove duplicates and sort
    
    def find_drug(self, drug_name: str) -> Optional[Dict]:
        """Find drug by name"""
        name_lower = drug_name.lower()
        if name_lower in self.name_index:
            return self.drugs[self.name_index[name_lower]]
        return None
    
    def get_summary(self, drug_name: str) -> Dict:
        """Get drug summary with all data, including OpenFDA data"""
        drug = self.find_drug(drug_name)
        if not drug:
            return {'error': f"Drug '{drug_name}' not found"}
        
        dosing = drug.get('dosing_info', {})
        
        # Try to get OpenFDA data for better dosing information
        openfda_dosing_data = self._get_openfda_dosing(drug_name)
        
        # Extract dosing data, checking OpenFDA first, then openfda_full
        frequency = dosing.get('frequency')
        times_per_day = dosing.get('times_per_day')
        routes = dosing.get('routes')
        
        # Check OpenFDA data first (more reliable)
        if openfda_dosing_data:
            if not frequency:
                frequency = openfda_dosing_data.get('frequency')
            if not times_per_day:
                times_per_day = openfda_dosing_data.get('times_per_day_range') or openfda_dosing_data.get('times_per_day')
            if not routes:
                routes = openfda_dosing_data.get('routes', [])
                if not routes and openfda_dosing_data.get('route'):
                    routes = [openfda_dosing_data['route']] if isinstance(openfda_dosing_data['route'], str) else []
        
        # Check openfda_full in comprehensive database
        openfda_full = dosing.get('openfda_full', {})
        if openfda_full:
            if not frequency:
                frequency = openfda_full.get('frequency')
            if not times_per_day:
                times_per_day = openfda_full.get('times_per_day_range') or openfda_full.get('times_per_day')
            if not routes:
                # Get route from openfda_full
                route = openfda_full.get('route')
                if route:
                    routes = [route] if isinstance(route, str) else route
        
        # Get instructions from OpenFDA or comprehensive database
        instructions = dosing.get('instructions', '')
        if not instructions and openfda_dosing_data:
            instructions = openfda_dosing_data.get('instructions', '')
        if not instructions and openfda_full:
            instructions = openfda_full.get('instructions', '')
        
        # If still no frequency, try to extract from instructions
        if not frequency and instructions:
            instructions_lower = instructions.lower()
            # Look for "once daily", "twice daily", etc.
            if re.search(r'\bonce\s+(?:a\s+)?daily\b', instructions_lower):
                frequency = 'Once daily'
                times_per_day = '1'
            elif re.search(r'\btwice\s+(?:a\s+)?daily\b', instructions_lower):
                frequency = 'Twice daily'
                times_per_day = '2'
            elif re.search(r'\bthree\s+times\s+daily\b', instructions_lower):
                frequency = 'Three times daily'
                times_per_day = '3'
            elif re.search(r'\bfour\s+times\s+daily\b', instructions_lower):
                frequency = 'Four times daily'
                times_per_day = '4'
        
        summary = {
            'name': drug.get('name'),
            'drugbank_id': drug.get('drugbank_ids', {}).get('primary'),
            'type': drug.get('type'),
            'groups': drug.get('groups', []),
            'description': drug.get('description', ''),
            
            # Dosing
            'dosing': {
                'has_dosing': dosing.get('has_dosing', False),
                'source': dosing.get('source'),
                'frequency': frequency,
                'times_per_day': times_per_day,
                'routes': routes
            },
            
            # Interactions
            'interaction_count': len(drug.get('drug_interactions', [])),
            'food_interactions': drug.get('food_interactions', []),
            'interactions_list': drug.get('drug_interactions', []),
            
            # Properties
            'properties': {},
            
            # Pharmacokinetics
            'pharmacokinetics': {
                'half_life': drug.get('half_life'),
                'absorption': drug.get('absorption'),
                'metabolism': drug.get('metabolism')
            },
            
            # Routes and forms
            'dosages': drug.get('dosages', [])
        }
        
        # Extract key properties
        for prop in drug.get('experimental_properties', []):
            kind = prop.get('kind')
            if kind in ['Melting Point', 'Water Solubility', 'Molecular Weight', 'logP', 'pKa']:
                summary['properties'][kind] = prop.get('value')
        
        return summary
    
    def _check_drug_class_interactions(self, drug1: Dict, drug2: Dict, drug1_name: str, drug2_name: str) -> List[Dict]:
        """
        Check for known drug class interactions that may not be in the database.
        Returns list of interaction dictionaries.
        """
        interactions = []
        
        # Get drug categories
        categories1 = []
        for cat in drug1.get('categories', []):
            normalized = self._normalize_category_name(cat)
            if normalized:
                categories1.append(normalized.lower())
        
        categories2 = []
        for cat in drug2.get('categories', []):
            normalized = self._normalize_category_name(cat)
            if normalized:
                categories2.append(normalized.lower())
        
        # Also check mechanism of action and description for drug class keywords
        moa1 = (drug1.get('mechanism_of_action', '') or '').lower()
        moa2 = (drug2.get('mechanism_of_action', '') or '').lower()
        desc1 = (drug1.get('description', '') or '').lower()
        desc2 = (drug2.get('description', '') or '').lower()
        
        # Check for benzodiazepine + beta-blocker interaction (e.g., Alprazolam + Nebivolol)
        benzodiazepine_keywords = ['benzodiazepine', 'alprazolam', 'diazepam', 'lorazepam', 'clonazepam', 
                                   'temazepam', 'oxazepam', 'chlordiazepoxide', 'midazolam']
        beta_blocker_keywords = ['beta-blocker', 'beta blocker', 'beta-adrenergic', 'nebivolol', 'propranolol',
                                 'metoprolol', 'atenolol', 'bisoprolol', 'carvedilol', 'labetalol']
        
        is_benzodiazepine = any(kw in ' '.join(categories1) or kw in moa1 or kw in desc1 
                               for kw in benzodiazepine_keywords) or \
                          any(kw in drug1_name.lower() for kw in ['alprazolam', 'xanax'])
        is_beta_blocker = any(kw in ' '.join(categories2) or kw in moa2 or kw in desc2 
                             for kw in beta_blocker_keywords) or \
                        any(kw in drug2_name.lower() for kw in ['nebivolol', 'propranolol', 'metoprolol'])
        
        # Check reverse direction
        if not is_benzodiazepine:
            is_benzodiazepine = any(kw in ' '.join(categories2) or kw in moa2 or kw in desc2 
                                   for kw in benzodiazepine_keywords) or \
                              any(kw in drug2_name.lower() for kw in ['alprazolam', 'xanax'])
        if not is_beta_blocker:
            is_beta_blocker = any(kw in ' '.join(categories1) or kw in moa1 or kw in desc1 
                                 for kw in beta_blocker_keywords) or \
                            any(kw in drug1_name.lower() for kw in ['nebivolol', 'propranolol', 'metoprolol'])
        
        if is_benzodiazepine and is_beta_blocker:
            interactions.append({
                'drug': drug2_name if is_beta_blocker and drug2_name.lower() in [kw for kw in beta_blocker_keywords if len(kw) > 5] else drug1_name,
                'description': 'Benzodiazepines and beta-blockers may have additive effects on blood pressure lowering and CNS depression. May cause increased drowsiness, dizziness, lightheadedness, fainting, and changes in heart rate. Monitor blood pressure and heart rate closely.',
                'severity': 'moderate',
                'source': 'known_class_interaction'
            })
        
        # Check for CNS depressants combination
        cns_depressant_keywords = ['cns depressant', 'sedative', 'hypnotic', 'anxiolytic', 'opioid', 
                                   'barbiturate', 'alcohol', 'antihistamine']
        is_cns_depressant1 = any(kw in ' '.join(categories1) or kw in moa1 or kw in desc1 
                                for kw in cns_depressant_keywords)
        is_cns_depressant2 = any(kw in ' '.join(categories2) or kw in moa2 or kw in desc2 
                                for kw in cns_depressant_keywords)
        
        if is_cns_depressant1 and is_cns_depressant2 and not (is_benzodiazepine and is_beta_blocker):
            interactions.append({
                'drug': drug2_name,
                'description': 'Both medications may cause CNS depression. Combined use may increase risk of drowsiness, dizziness, and impaired coordination. Use with caution.',
                'severity': 'moderate',
                'source': 'known_class_interaction'
            })
        
        return interactions
    
    def check_compatibility(self, drug1_name: str, drug2_name: str) -> Dict:
        """Check 3D printing compatibility"""
        result = {
            'drug1': drug1_name,
            'drug2': drug2_name,
            'compatible': True,
            'issues': [],
            'warnings': [],
            'recommendations': [],
            'drug1_data': None,
            'drug2_data': None
        }
        
        drug1 = self.find_drug(drug1_name)
        drug2 = self.find_drug(drug2_name)
        
        if not drug1:
            result['issues'].append(f"Drug '{drug1_name}' not found in database")
            result['compatible'] = False
            return result
        
        if not drug2:
            result['issues'].append(f"Drug '{drug2_name}' not found in database")
            result['compatible'] = False
            return result
        
        # Store drug data for display
        result['drug1_data'] = self.get_summary(drug1_name)
        result['drug2_data'] = self.get_summary(drug2_name)
        
        # Check biologics
        if drug1.get('type') == 'biotech':
            result['issues'].append(f"{drug1_name} is a biologic (protein/antibody) - cannot be 3D printed with standard methods")
            result['compatible'] = False
        
        if drug2.get('type') == 'biotech':
            result['issues'].append(f"{drug2_name} is a biologic (protein/antibody) - cannot be 3D printed with standard methods")
            result['compatible'] = False
        
        # Check dosing frequency (with fallback to openfda_full and instructions parsing)
        dosing1 = drug1.get('dosing_info', {})
        dosing2 = drug2.get('dosing_info', {})
        
        # Helper function to extract dosing with fallbacks (including OpenFDA)
        def extract_dosing(dosing, drug_name):
            """Extract frequency and times_per_day with fallbacks from OpenFDA and comprehensive database"""
            frequency = dosing.get('frequency')
            times_per_day = dosing.get('times_per_day')
            
            # Try to get OpenFDA data first (most reliable)
            openfda_dosing_data = self._get_openfda_dosing(drug_name)
            
            # Check OpenFDA data first
            if openfda_dosing_data:
                if not frequency:
                    frequency = openfda_dosing_data.get('frequency')
                if not times_per_day:
                    times_per_day = openfda_dosing_data.get('times_per_day_range') or openfda_dosing_data.get('times_per_day')
            
            # Check openfda_full in comprehensive database
            openfda_full = dosing.get('openfda_full', {})
            if openfda_full:
                if not frequency:
                    frequency = openfda_full.get('frequency')
                if not times_per_day:
                    times_per_day = openfda_full.get('times_per_day_range') or openfda_full.get('times_per_day')
            
            # Get instructions from OpenFDA or comprehensive database
            instructions = dosing.get('instructions', '')
            if not instructions and openfda_dosing_data:
                instructions = openfda_dosing_data.get('instructions', '')
            if not instructions and openfda_full:
                instructions = openfda_full.get('instructions', '')
            
            # Parse from instructions if still missing
            if not frequency and instructions:
                instructions_lower = instructions.lower()
                if re.search(r'\bonce\s+(?:a\s+)?daily\b', instructions_lower):
                    frequency = 'Once daily'
                    times_per_day = '1'
                elif re.search(r'\btwice\s+(?:a\s+)?daily\b', instructions_lower):
                    frequency = 'Twice daily'
                    times_per_day = '2'
                elif re.search(r'\bthree\s+times\s+daily\b', instructions_lower):
                    frequency = 'Three times daily'
                    times_per_day = '3'
                elif re.search(r'\bfour\s+times\s+daily\b', instructions_lower):
                    frequency = 'Four times daily'
                    times_per_day = '4'
            
            return frequency, times_per_day
        
        freq1, times1 = extract_dosing(dosing1, drug1_name)
        freq2, times2 = extract_dosing(dosing2, drug2_name)
        
        # Always store dosing data if we have any
        result['dosing'] = {
            'drug1': {'frequency': freq1, 'times_per_day': times1},
            'drug2': {'frequency': freq2, 'times_per_day': times2}
        }
        
        # Only compare if both have dosing data
        if (freq1 or times1) and (freq2 or times2):
            if times1 and times2 and times1 == times2:
                result['recommendations'].append(f"📊 Same dosing frequency: both {freq1 or 'N/A'} ({times1}x/day)")
            elif times1 and times2:
                result['warnings'].append(f"⚠️ Different dosing frequencies: {freq1 or 'N/A'} ({times1}x/day) vs {freq2 or 'N/A'} ({times2}x/day)")
                result['recommendations'].append(f"📊 Timed-release formulation or separate administration may be needed")
        else:
            if not (freq1 or times1):
                result['warnings'].append(f"⚠️ No dosing frequency data available for {drug1_name}")
            if not (freq2 or times2):
                result['warnings'].append(f"⚠️ No dosing frequency data available for {drug2_name}")
        
        # Collect routes of administration (normalize to lowercase for comparison)
        routes1 = set()
        routes2 = set()
        routes1_original = {}  # Store original case for display
        routes2_original = {}  # Store original case for display
        
        # Helper function to normalize route
        def normalize_route(route_str):
            """Normalize route to lowercase for comparison"""
            if not isinstance(route_str, str):
                return None
            return route_str.lower().strip()
        
        # Helper function to extract routes from dosing info (including openfda_full)
        def extract_routes(dosing):
            """Extract all routes from dosing_info, including openfda_full"""
            routes = []
            # Get from main routes field
            if dosing.get('routes'):
                route_data = dosing.get('routes')
                if isinstance(route_data, list):
                    routes.extend(route_data)
                elif isinstance(route_data, str):
                    routes.append(route_data)
            
            # Get from openfda_full
            openfda_full = dosing.get('openfda_full', {})
            if openfda_full:
                # Check routes array
                if openfda_full.get('routes'):
                    route_data = openfda_full.get('routes')
                    if isinstance(route_data, list):
                        routes.extend(route_data)
                    elif isinstance(route_data, str):
                        routes.append(route_data)
                # Check single route field
                if openfda_full.get('route'):
                    route = openfda_full.get('route')
                    if isinstance(route, str):
                        routes.append(route)
            
            return routes
        
        # Extract routes for both drugs
        routes1_list = extract_routes(dosing1)
        routes2_list = extract_routes(dosing2)
        
        # Normalize and add routes
        for route in routes1_list:
            if isinstance(route, str):
                normalized = normalize_route(route)
                if normalized:
                    routes1.add(normalized)
                    routes1_original[normalized] = route  # Keep original case
        
        for route in routes2_list:
            if isinstance(route, str):
                normalized = normalize_route(route)
                if normalized:
                    routes2.add(normalized)
                    routes2_original[normalized] = route  # Keep original case
        
        # Get routes from dosages
        for d in drug1.get('dosages', []):
            if d and d.get('route'):
                route = d.get('route')
                normalized = normalize_route(route)
                if normalized:
                    routes1.add(normalized)
                    routes1_original[normalized] = route  # Keep original case
        for d in drug2.get('dosages', []):
            if d and d.get('route'):
                route = d.get('route')
                normalized = normalize_route(route)
                if normalized:
                    routes2.add(normalized)
                    routes2_original[normalized] = route  # Keep original case
        
        # Find common routes (case-insensitive comparison)
        common_normalized = routes1.intersection(routes2)
        
        # Convert back to original case for display
        routes1_display = [routes1_original.get(r, r.title()) for r in sorted(routes1)]
        routes2_display = [routes2_original.get(r, r.title()) for r in sorted(routes2)]
        common_display = [routes1_original.get(r, routes2_original.get(r, r.title())) for r in sorted(common_normalized)]
        
        # Store routes in result
        result['routes'] = {
            'drug1': routes1_display if routes1_display else [],
            'drug2': routes2_display if routes2_display else [],
            'common': common_display if common_display else []
        }
        
        # Check interactions
        drug2_id = drug2.get('drugbank_ids', {}).get('primary')
        drug1_id = drug1.get('drugbank_ids', {}).get('primary')
        
        # Also check secondary IDs for interactions
        drug1_secondary_ids = drug1.get('drugbank_ids', {}).get('secondary', [])
        drug2_secondary_ids = drug2.get('drugbank_ids', {}).get('secondary', [])
        
        # Store all interactions found
        interactions_found = []
        
        # Check drug1 -> drug2 interactions
        for interaction in drug1.get('drug_interactions', []):
            interaction_id = interaction.get('drugbank_id')
            if interaction_id == drug2_id or interaction_id in drug2_secondary_ids:
                desc = interaction.get('description', '')
                drug_name = interaction.get('name', drug2_name)
                interactions_found.append({
                    'drug': drug_name,
                    'description': desc,
                    'severity': 'severe' if any(w in desc.lower() for w in ['severe', 'contraindicated', 'should not', 'dangerous']) else 'moderate'
                })
                if any(w in desc.lower() for w in ['severe', 'contraindicated', 'should not', 'dangerous']):
                    result['issues'].append(f"❌ SEVERE INTERACTION: {desc}")
                    result['compatible'] = False
                else:
                    result['warnings'].append(f"⚠️ Interaction detected: {desc}")
        
        # Check drug2 -> drug1 interactions (reverse direction)
        for interaction in drug2.get('drug_interactions', []):
            interaction_id = interaction.get('drugbank_id')
            if interaction_id == drug1_id or interaction_id in drug1_secondary_ids:
                desc = interaction.get('description', '')
                drug_name = interaction.get('name', drug1_name)
                # Avoid duplicates
                if not any(i['description'] == desc for i in interactions_found):
                    interactions_found.append({
                        'drug': drug_name,
                        'description': desc,
                        'severity': 'severe' if any(w in desc.lower() for w in ['severe', 'contraindicated', 'should not', 'dangerous']) else 'moderate'
                    })
                    if any(w in desc.lower() for w in ['severe', 'contraindicated', 'should not', 'dangerous']):
                        if f"❌ SEVERE INTERACTION: {desc}" not in result['issues']:
                            result['issues'].append(f"❌ SEVERE INTERACTION: {desc}")
                            result['compatible'] = False
                    else:
                        if f"⚠️ Interaction detected: {desc}" not in result['warnings']:
                            result['warnings'].append(f"⚠️ Interaction detected: {desc}")
        
        # Check for known drug class interactions (fallback when not in database)
        known_class_interactions = self._check_drug_class_interactions(drug1, drug2, drug1_name, drug2_name)
        if known_class_interactions:
            for interaction in known_class_interactions:
                # Avoid duplicates
                if not any(i.get('description', '').lower() == interaction['description'].lower() for i in interactions_found):
                    interactions_found.append(interaction)
                    result['warnings'].append(f"⚠️ Potential class-based interaction: {interaction['description']}")
        
        # Store interactions in result
        result['interactions'] = interactions_found
        
        # Add general observations
        if result['compatible']:
            result['recommendations'].append(f"📊 Drug types: {drug1.get('type', 'unknown')} + {drug2.get('type', 'unknown')}")
            
            # Routes already collected above
            if result['routes']['common']:
                result['recommendations'].append(f"🛣️ Common routes of administration: {', '.join(result['routes']['common'][:5])}")
            elif result['routes']['drug1'] or result['routes']['drug2']:
                routes1_str = ', '.join(result['routes']['drug1'][:3]) if result['routes']['drug1'] else 'Unknown'
                routes2_str = ', '.join(result['routes']['drug2'][:3]) if result['routes']['drug2'] else 'Unknown'
                result['recommendations'].append(f"🛣️ Routes: {drug1_name} ({routes1_str}) vs {drug2_name} ({routes2_str})")
        
        return result


@st.cache_resource
def load_database():
    """Load and cache the database"""
    with st.spinner("Loading drug database... This may take a moment..."):
        db = ComprehensiveDrugQuery()
    return db


def display_drug_card(drug_summary: Dict, title: str):
    """Display a drug information card with comprehensive data"""
    st.subheader(title)
    
    # Drug Type, Status, and Interactions - PROMINENT
    col1, col2, col3 = st.columns(3)
    
    with col1:
        drug_type = drug_summary.get('type', 'Unknown')
        if drug_type:
            st.metric("Drug Type", drug_type.title() if isinstance(drug_type, str) else str(drug_type))
        else:
            st.metric("Drug Type", "Unknown")
    
    with col2:
        groups = drug_summary.get('groups', [])
        if groups:
            status = ', '.join([g.title() if isinstance(g, str) else str(g) for g in groups])
            st.metric("Status", status)
        else:
            st.metric("Status", "Unknown")
    
    with col3:
        interaction_count = drug_summary.get('interaction_count', 0)
        st.metric("Interactions", interaction_count)
    
    # Routes of Administration - PROMINENT
    routes_set = set()
    # Get routes from dosing_info
    if drug_summary.get('dosing', {}).get('routes'):
        for route in drug_summary['dosing']['routes']:
            if isinstance(route, str):
                routes_set.add(route)
    # Get routes from dosages
    for d in drug_summary.get('dosages', []):
        if d and d.get('route'):
            routes_set.add(d.get('route'))
    
    if routes_set:
        st.markdown("### 🛣️ Routes of Administration")
        routes_list = sorted(list(routes_set))
        # Display as badges
        route_badges = " ".join([f"`{route}`" for route in routes_list[:10]])
        st.markdown(route_badges)
        if len(routes_list) > 10:
            st.caption(f"... and {len(routes_list) - 10} more routes")
    else:
        st.info("### 🛣️ Routes of Administration: No route data available")
    
    # Drug Interactions - PROMINENT (Full text, no truncation)
    if drug_summary.get('interactions_list'):
        st.markdown("### 🔗 Drug Interactions")
        with st.expander(f"View {drug_summary['interaction_count']} interactions", expanded=True):
            for i, interaction in enumerate(drug_summary['interactions_list'], 1):
                drug_name = interaction.get('name', 'Unknown')
                description = interaction.get('description', 'No description available')
                
                # Check if severe
                is_severe = any(word in description.lower() for word in ['severe', 'contraindicated', 'should not', 'dangerous'])
                
                # Create a container for each interaction
                with st.container():
                    if is_severe:
                        st.error(f"**{i}. {drug_name}**")
                        st.markdown(description)
                    else:
                        st.warning(f"**{i}. {drug_name}**")
                        st.markdown(description)
                    
                    # Add separator between interactions (but not after the last one)
                    if i < len(drug_summary['interactions_list']):
                        st.markdown("---")
    else:
        st.info("### 🔗 Drug Interactions: No known drug interactions")
    
    # Description - Full text (no truncation)
    if drug_summary.get('description'):
        with st.expander("📖 Description", expanded=False):
            st.write(drug_summary['description'])
    
    # Dosing Information - PROMINENT
    st.markdown("### 💊 Dosing Information")
    dosing = drug_summary['dosing']
    if dosing.get('has_dosing'):
        col1, col2 = st.columns(2)
        with col1:
            if dosing.get('frequency'):
                st.write(f"**Frequency:** {dosing['frequency']}")
            if dosing.get('times_per_day'):
                st.write(f"**Times per day:** {dosing['times_per_day']}x")
            if dosing.get('routes'):
                routes_str = ', '.join(dosing['routes'][:5]) if isinstance(dosing['routes'], list) else str(dosing['routes'])
                st.write(f"**Routes:** {routes_str}")
        with col2:
            if dosing.get('source'):
                st.write(f"**Source:** {dosing['source']}")
    else:
        st.warning("No dosing frequency data available")
    
    # Physical Properties
    if drug_summary.get('properties'):
        with st.expander("🔬 Physical Properties", expanded=False):
            for key, value in drug_summary['properties'].items():
                st.write(f"**{key}:** {value}")
    
    # Dosage Forms
    if drug_summary.get('dosages'):
        with st.expander("📦 Available Dosage Forms", expanded=False):
            for i, d in enumerate(drug_summary['dosages'][:10], 1):
                form = d.get('form', 'N/A')
                route = d.get('route', 'N/A')
                strength = d.get('strength', 'N/A')
                st.write(f"{i}. **{form}** - Route: {route} - Strength: {strength}")
            if len(drug_summary['dosages']) > 10:
                st.info(f"... and {len(drug_summary['dosages']) - 10} more dosage forms")


def main():
    st.set_page_config(
        page_title="Drug Assessment Tool",
        page_icon="💊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
        <style>
        .stAlert > div {
            padding: 1rem;
        }
        .metric-container {
            background-color: #f0f2f6;
            padding: 1rem;
            border-radius: 0.5rem;
            margin: 0.5rem 0;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Sidebar - How it works / toggle
    with st.sidebar:
        if st.session_state['active_app'] == 'drug':
            st.markdown("---")
            st.subheader("🔍 What This Tool Provides")
            st.markdown("""
            This assessment tool analyzes:
            
            1. **Drug Type**
               - Small molecules vs biologics
               - Suitability for 3D printing methods
            
            2. **Dosing Frequency**
               - Times per day comparison
               - Schedule compatibility
            
            3. **Drug Interactions**
               - Known drug-drug interactions
               - Severity and descriptions
            
            4. **Physical Properties**
               - Melting point, solubility, etc.
               - Routes of administration
            
            **Experts should evaluate all findings to determine compatibility.**
            """)
            
            st.markdown("---")
            st.markdown("**⚠️ Disclaimer:** This is an information tool. All findings require expert evaluation before any clinical decisions.")
        
        st.markdown("---")
        st.subheader("⚙️ Launch Other Tools")
        if st.session_state['active_app'] == 'drug':
            if st.button("Open Athero App", use_container_width=True):
                st.session_state['active_app'] = 'athero'
                _rerun_app()
            st.caption("Launches the embedded Athero research tool in this window.")
        else:
            st.success("Athero App is active.")
            if st.button("Return to Drug App", use_container_width=True):
                st.session_state['active_app'] = 'drug'
                _rerun_app()
            st.caption("Use the button above to go back to the Drug Compatibility tool.")
    
    if st.session_state['active_app'] == 'athero':
        render_athero_app()
        return
    
    st.title("💊 Drug Interaction & 3D Printing Assessment Tool")
    st.markdown("**Analyze drug interactions, dosing schedules, and properties for expert evaluation**")
    
    # Load database
    try:
        db = load_database()
        st.sidebar.success(f"✅ Database loaded: {len(db.drugs):,} drugs")
        st.sidebar.info(f"📊 Drugs with dosing data: {db.metadata.get('drugs_with_dosing', 0):,}")
    except Exception as e:
        st.error(f"❌ Error loading database: {e}")
        st.info("Please ensure either 'comprehensive_drug_database_compact.json' or 'comprehensive_drug_database.json' is in the same directory.")
        return
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 Check Compatibility", "📊 Single Drug Info", "📚 Search Database", "🏷️ Category-Based Selection", "🤖 AI Drug Agent"])
    
    # Tab 1: Compatibility Check
    with tab1:
        st.header("Drug Interaction & Properties Assessment")
        st.markdown("Analyze two drugs to review interactions, dosing, and properties for expert evaluation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Drug 1")
            drug1_search = st.text_input(
                "Search for first drug:",
                key="drug1_search",
                placeholder="Start typing drug name..."
            )
            
            if drug1_search and len(drug1_search) >= 2:
                results1 = db.search_drugs(drug1_search)
                drug1 = st.selectbox(
                    "Select drug 1:",
                    options=[""] + results1,
                    key="drug1_select"
                )
            else:
                drug1 = ""
                if not drug1_search:
                    st.info("👆 Type at least 2 characters to search")
        
        with col2:
            st.subheader("Drug 2")
            drug2_search = st.text_input(
                "Search for second drug:",
                key="drug2_search",
                placeholder="Start typing drug name..."
            )
            
            if drug2_search and len(drug2_search) >= 2:
                results2 = db.search_drugs(drug2_search)
                drug2 = st.selectbox(
                    "Select drug 2:",
                    options=[""] + results2,
                    key="drug2_select"
                )
            else:
                drug2 = ""
                if not drug2_search:
                    st.info("👆 Type at least 2 characters to search")
        
        st.markdown("---")
        
        if st.button("🔍 Analyze Drugs", type="primary", use_container_width=True):
            if drug1 and drug2:
                with st.spinner("Analyzing drug data..."):
                    result = db.check_compatibility(drug1, drug2)
                
                # Display assessment results
                st.markdown(f"## 📋 Assessment Results: {drug1} + {drug2}")
                
                # Routes of Administration - PROMINENT
                if 'routes' in result:
                    st.markdown("### 🛣️ Routes of Administration")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        routes1 = result['routes'].get('drug1', [])
                        if routes1:
                            st.markdown(f"**{drug1}:**")
                            route_badges1 = " ".join([f"`{r}`" for r in routes1[:5]])
                            st.markdown(route_badges1)
                        else:
                            st.info(f"**{drug1}:** No route data")
                    
                    with col2:
                        routes2 = result['routes'].get('drug2', [])
                        if routes2:
                            st.markdown(f"**{drug2}:**")
                            route_badges2 = " ".join([f"`{r}`" for r in routes2[:5]])
                            st.markdown(route_badges2)
                        else:
                            st.info(f"**{drug2}:** No route data")
                    
                    with col3:
                        common = result['routes'].get('common', [])
                        if common:
                            st.success("**Common Routes:**")
                            common_badges = " ".join([f"`{r}`" for r in common[:5]])
                            st.markdown(common_badges)
                        else:
                            st.warning("**No common routes**")
                    
                    st.markdown("---")
                
                # Drug Interactions - PROMINENT
                if 'interactions' in result and result['interactions']:
                    st.markdown("### 🔗 Drug Interactions")
                    
                    severe_interactions = [i for i in result['interactions'] if i['severity'] == 'severe']
                    moderate_interactions = [i for i in result['interactions'] if i['severity'] == 'moderate']
                    
                    if severe_interactions:
                        st.error(f"**{len(severe_interactions)} Severe Interaction(s) Found:**")
                        for interaction in severe_interactions:
                            st.markdown(f"❌ **{interaction['drug']}** - {interaction['description']}")
                    
                    if moderate_interactions:
                        st.warning(f"**{len(moderate_interactions)} Moderate Interaction(s) Found:**")
                        for interaction in moderate_interactions:
                            st.markdown(f"⚠️ **{interaction['drug']}** - {interaction['description']}")
                    
                    st.markdown("---")
                elif 'interactions' in result:
                    st.success("### 🔗 Drug Interactions: ✅ No known interactions detected")
                    st.markdown("---")
                
                # Display critical findings
                if result['issues']:
                    st.error("### 🚨 Critical Findings")
                    for issue in result['issues']:
                        st.markdown(f"- {issue}")
                
                # Display warnings
                if result['warnings']:
                    st.warning("### ⚠️ Warnings & Considerations")
                    for warning in result['warnings']:
                        st.markdown(f"- {warning}")
                
                # Display observations
                if result['recommendations']:
                    st.info("### 📊 Observations")
                    for rec in result['recommendations']:
                        st.markdown(f"- {rec}")
                
                # Dosing comparison
                if 'dosing' in result:
                    st.markdown("### 📅 Dosing Comparison")
                    col1, col2 = st.columns(2)
                    with col1:
                        times1 = result['dosing']['drug1'].get('times_per_day')
                        freq1 = result['dosing']['drug1'].get('frequency')
                        if times1:
                            st.metric(
                                f"{drug1}",
                                f"{times1}x/day",
                                freq1 or "Frequency not specified"
                            )
                        else:
                            st.metric(
                                f"{drug1}",
                                "No dosing data",
                                freq1 or "Frequency not specified"
                            )
                    with col2:
                        times2 = result['dosing']['drug2'].get('times_per_day')
                        freq2 = result['dosing']['drug2'].get('frequency')
                        if times2:
                            st.metric(
                                f"{drug2}",
                                f"{times2}x/day",
                                freq2 or "Frequency not specified"
                            )
                        else:
                            st.metric(
                                f"{drug2}",
                                "No dosing data",
                                freq2 or "Frequency not specified"
                            )
                
                # Detailed drug information
                st.markdown("---")
                st.markdown("## 📊 Detailed Drug Information")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if result['drug1_data']:
                        display_drug_card(result['drug1_data'], f"💊 {drug1}")
                
                with col2:
                    if result['drug2_data']:
                        display_drug_card(result['drug2_data'], f"💊 {drug2}")
            
            else:
                st.warning("⚠️ Please select both drugs to analyze")
    
    # Tab 2: Single Drug Info
    with tab2:
        st.header("Single Drug Information")
        st.markdown("Search and view detailed information about a specific drug")
        
        # Use session state to handle drug selection from other tabs
        if 'selected_single_drug' not in st.session_state:
            st.session_state['selected_single_drug'] = ""
        
        drug_search = st.text_input(
            "Search for drug:",
            value=st.session_state.get('selected_single_drug', ''),
            key="single_drug_search",
            placeholder="Start typing drug name..."
        )
        
        if drug_search and len(drug_search) >= 2:
            results = db.search_drugs(drug_search)
            selected_drug = st.selectbox(
                "Select drug:",
                options=[""] + results,
                key="single_drug_select"
            )
            
            if selected_drug:
                summary = db.get_summary(selected_drug)
                
                if 'error' not in summary:
                    display_drug_card(summary, f"💊 {selected_drug}")
                    
                    # Show sample interactions
                    if summary['interactions_list']:
                        with st.expander(f"🔗 Sample Interactions ({len(summary['interactions_list'])} total)"):
                            for i, interaction in enumerate(summary['interactions_list'][:10]):
                                st.markdown(f"**{i+1}. {interaction.get('name', 'N/A')}**")
                                st.write(interaction.get('description', 'No description'))
                                st.markdown("---")
                            if len(summary['interactions_list']) > 10:
                                st.info(f"Showing 10 of {len(summary['interactions_list'])} interactions")
                else:
                    st.error(summary['error'])
        else:
            st.info("👆 Type at least 2 characters to search")
    
    # Tab 3: Search Database
    with tab3:
        st.header("Search Drug Database")
        st.markdown("Browse and search the entire drug database")
        
        # Initialize session state for selected browse drug
        if 'selected_browse_drug' not in st.session_state:
            st.session_state['selected_browse_drug'] = None
        
        search_query = st.text_input(
            "Search drugs:",
            key="browse_search",
            placeholder="Enter search term..."
        )
        
        if search_query and len(search_query) >= 2:
            results = db.search_drugs(search_query)
            
            st.success(f"Found {len(results)} drugs matching '{search_query}'")
            
            if results:
                # Display in columns
                cols = st.columns(3)
                for i, drug_name in enumerate(results):
                    with cols[i % 3]:
                        if st.button(drug_name, key=f"browse_{i}"):
                            st.session_state['selected_browse_drug'] = drug_name
            else:
                st.warning("No drugs found matching your search")
        else:
            st.info("👆 Type at least 2 characters to search")
            
            # Show some example drugs
            st.markdown("### 💡 Example Drugs to Try")
            examples = ["Metformin", "Aspirin", "Ibuprofen", "Lisinopril", "Atorvastatin", 
                       "Amlodipine", "Metoprolol", "Omeprazole", "Levothyroxine", "Albuterol"]
            
            cols = st.columns(5)
            for i, example in enumerate(examples):
                with cols[i % 5]:
                    if st.button(example, key=f"example_{i}"):
                        st.session_state['selected_browse_drug'] = example
        
        # Display selected drug info
        if st.session_state['selected_browse_drug']:
            st.markdown("---")
            st.markdown(f"## 📊 Drug Information")
            
            selected = st.session_state['selected_browse_drug']
            summary = db.get_summary(selected)
            
            if 'error' not in summary:
                display_drug_card(summary, f"💊 {selected}")
                
                # Show sample interactions
                if summary['interactions_list']:
                    with st.expander(f"🔗 Sample Interactions ({len(summary['interactions_list'])} total)"):
                        for i, interaction in enumerate(summary['interactions_list'][:10]):
                            st.markdown(f"**{i+1}. {interaction.get('name', 'N/A')}**")
                            st.write(interaction.get('description', 'No description'))
                            st.markdown("---")
                        if len(summary['interactions_list']) > 10:
                            st.info(f"Showing 10 of {len(summary['interactions_list'])} interactions")
                
                # Clear button
                if st.button("🔄 Clear Selection", key="clear_browse"):
                    st.session_state['selected_browse_drug'] = None
                    st.rerun()
            else:
                st.error(summary['error'])
    
    # Tab 4: Category-Based Selection
    with tab4:
        st.header("Category-Based Drug Selection")
        st.markdown("Select categories and drugs for each drug to check interactions")
        
        # Initialize session state
        if 'cat1_selected' not in st.session_state:
            st.session_state['cat1_selected'] = None
        if 'drug1_selected' not in st.session_state:
            st.session_state['drug1_selected'] = None
        if 'cat2_selected' not in st.session_state:
            st.session_state['cat2_selected'] = None
        if 'drug2_selected' not in st.session_state:
            st.session_state['drug2_selected'] = None
        
        all_categories = db.get_all_categories()
        
        col1, col2 = st.columns(2)
        
        # Drug 1 Selection
        with col1:
            st.subheader("Drug 1")
            
            # Category selection for Drug 1
            st.markdown("**Step 1: Choose Category**")
            cat1_search = st.text_input(
                "Search categories:",
                key="cat1_search",
                placeholder="e.g., NSAID, Antibiotic..."
            )
            
            if cat1_search and len(cat1_search) >= 2:
                filtered_cats1 = [cat for cat in all_categories 
                                 if cat1_search.lower() in cat.lower()]
                if filtered_cats1:
                    selected_cat1 = st.selectbox(
                        "Select category:",
                        options=[""] + filtered_cats1,
                        key="cat1_select",
                        index=0 if st.session_state['cat1_selected'] not in filtered_cats1 else filtered_cats1.index(st.session_state['cat1_selected']) + 1
                    )
                else:
                    selected_cat1 = None
                    st.warning("No categories found")
            else:
                # Show popular categories
                popular_categories = [
                    "Anti-Inflammatory Agents, Non-Steroidal",
                    "Antibiotics",
                    "Antidepressants",
                    "Antihypertensive Agents",
                    "Anticoagulants",
                    "Analgesics",
                    "Antidiabetic Agents",
                    "Antipsychotic Agents"
                ]
                available_popular = [cat for cat in popular_categories if cat in all_categories]
                
                if available_popular:
                    st.markdown("**Popular:**")
                    for i, cat in enumerate(available_popular[:4]):
                        if st.button(cat[:25] + "..." if len(cat) > 25 else cat, key=f"cat1_btn_{i}"):
                            st.session_state['cat1_selected'] = cat
                            st.rerun()
                
                selected_cat1 = st.selectbox(
                    "Or select category:",
                    options=[""] + all_categories[:100],
                    key="cat1_select_all"
                )
            
            if selected_cat1:
                st.session_state['cat1_selected'] = selected_cat1
                
                # Drug selection for Drug 1
                st.markdown("**Step 2: Choose Drug**")
                drugs1 = db.get_drugs_by_category(selected_cat1)
                
                if drugs1:
                    st.success(f"Found {len(drugs1)} drugs")
                    selected_drug1 = st.selectbox(
                        "Select drug:",
                        options=[""] + drugs1,
                        key="drug1_select",
                        index=0 if st.session_state['drug1_selected'] not in drugs1 else drugs1.index(st.session_state['drug1_selected']) + 1
                    )
                    
                    if selected_drug1:
                        st.session_state['drug1_selected'] = selected_drug1
                        st.info(f"✅ Selected: **{selected_drug1}**")
                else:
                    st.warning("No drugs in this category")
                    selected_drug1 = None
            else:
                selected_drug1 = None
                st.info("👆 Select a category first")
        
        # Drug 2 Selection
        with col2:
            st.subheader("Drug 2")
            
            # Category selection for Drug 2
            st.markdown("**Step 1: Choose Category**")
            cat2_search = st.text_input(
                "Search categories:",
                key="cat2_search",
                placeholder="e.g., NSAID, Antibiotic..."
            )
            
            if cat2_search and len(cat2_search) >= 2:
                filtered_cats2 = [cat for cat in all_categories 
                                 if cat2_search.lower() in cat.lower()]
                if filtered_cats2:
                    selected_cat2 = st.selectbox(
                        "Select category:",
                        options=[""] + filtered_cats2,
                        key="cat2_select",
                        index=0 if st.session_state['cat2_selected'] not in filtered_cats2 else filtered_cats2.index(st.session_state['cat2_selected']) + 1
                    )
                else:
                    selected_cat2 = None
                    st.warning("No categories found")
            else:
                # Show popular categories
                popular_categories = [
                    "Anti-Inflammatory Agents, Non-Steroidal",
                    "Antibiotics",
                    "Antidepressants",
                    "Antihypertensive Agents",
                    "Anticoagulants",
                    "Analgesics",
                    "Antidiabetic Agents",
                    "Antipsychotic Agents"
                ]
                available_popular = [cat for cat in popular_categories if cat in all_categories]
                
                if available_popular:
                    st.markdown("**Popular:**")
                    for i, cat in enumerate(available_popular[:4]):
                        if st.button(cat[:25] + "..." if len(cat) > 25 else cat, key=f"cat2_btn_{i}"):
                            st.session_state['cat2_selected'] = cat
                            st.rerun()
                
                selected_cat2 = st.selectbox(
                    "Or select category:",
                    options=[""] + all_categories[:100],
                    key="cat2_select_all"
                )
            
            if selected_cat2:
                st.session_state['cat2_selected'] = selected_cat2
                
                # Drug selection for Drug 2
                st.markdown("**Step 2: Choose Drug**")
                drugs2 = db.get_drugs_by_category(selected_cat2)
                
                if drugs2:
                    st.success(f"Found {len(drugs2)} drugs")
                    selected_drug2 = st.selectbox(
                        "Select drug:",
                        options=[""] + drugs2,
                        key="drug2_select",
                        index=0 if st.session_state['drug2_selected'] not in drugs2 else drugs2.index(st.session_state['drug2_selected']) + 1
                    )
                    
                    if selected_drug2:
                        st.session_state['drug2_selected'] = selected_drug2
                        st.info(f"✅ Selected: **{selected_drug2}**")
                else:
                    st.warning("No drugs in this category")
                    selected_drug2 = None
            else:
                selected_drug2 = None
                st.info("👆 Select a category first")
        
        st.markdown("---")
        
        # Interaction Analysis
        if selected_drug1 and selected_drug2:
            st.subheader("Interaction Analysis")
            
            if st.button("🔍 Check Interactions", type="primary", use_container_width=True):
                with st.spinner("Analyzing drug data..."):
                    result = db.check_compatibility(selected_drug1, selected_drug2)
                
                # Display assessment results
                st.markdown(f"## 📋 Assessment Results: {selected_drug1} + {selected_drug2}")
                
                # Routes of Administration - PROMINENT
                if 'routes' in result:
                    st.markdown("### 🛣️ Routes of Administration")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        routes1 = result['routes'].get('drug1', [])
                        if routes1:
                            st.markdown(f"**{selected_drug1}:**")
                            route_badges1 = " ".join([f"`{r}`" for r in routes1[:5]])
                            st.markdown(route_badges1)
                        else:
                            st.info(f"**{selected_drug1}:** No route data")
                    
                    with col2:
                        routes2 = result['routes'].get('drug2', [])
                        if routes2:
                            st.markdown(f"**{selected_drug2}:**")
                            route_badges2 = " ".join([f"`{r}`" for r in routes2[:5]])
                            st.markdown(route_badges2)
                        else:
                            st.info(f"**{selected_drug2}:** No route data")
                    
                    with col3:
                        common = result['routes'].get('common', [])
                        if common:
                            st.success("**Common Routes:**")
                            common_badges = " ".join([f"`{r}`" for r in common[:5]])
                            st.markdown(common_badges)
                        else:
                            st.warning("**No common routes**")
                    
                    st.markdown("---")
                
                # Drug Interactions - PROMINENT
                if 'interactions' in result and result['interactions']:
                    st.markdown("### 🔗 Drug Interactions")
                    
                    severe_interactions = [i for i in result['interactions'] if i['severity'] == 'severe']
                    moderate_interactions = [i for i in result['interactions'] if i['severity'] == 'moderate']
                    
                    if severe_interactions:
                        st.error(f"**{len(severe_interactions)} Severe Interaction(s) Found:**")
                        for interaction in severe_interactions:
                            st.markdown(f"❌ **{interaction['drug']}** - {interaction['description']}")
                    
                    if moderate_interactions:
                        st.warning(f"**{len(moderate_interactions)} Moderate Interaction(s) Found:**")
                        for interaction in moderate_interactions:
                            st.markdown(f"⚠️ **{interaction['drug']}** - {interaction['description']}")
                    
                    st.markdown("---")
                elif 'interactions' in result:
                    st.success("### 🔗 Drug Interactions: ✅ No known interactions detected")
                    st.markdown("---")
                
                # Display critical findings
                if result['issues']:
                    st.error("### 🚨 Critical Findings")
                    for issue in result['issues']:
                        st.markdown(f"- {issue}")
                
                # Display warnings
                if result['warnings']:
                    st.warning("### ⚠️ Warnings & Considerations")
                    for warning in result['warnings']:
                        st.markdown(f"- {warning}")
                
                # Display observations
                if result['recommendations']:
                    st.info("### 📊 Observations")
                    for rec in result['recommendations']:
                        st.markdown(f"- {rec}")
                
                # Dosing comparison
                if 'dosing' in result:
                    st.markdown("### 📅 Dosing Comparison")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            f"{selected_drug1}",
                            f"{result['dosing']['drug1']['times_per_day']}x/day",
                            result['dosing']['drug1']['frequency']
                        )
                    with col2:
                        st.metric(
                            f"{selected_drug2}",
                            f"{result['dosing']['drug2']['times_per_day']}x/day",
                            result['dosing']['drug2']['frequency']
                        )
                
                # Detailed drug information
                st.markdown("---")
                st.markdown("## 📊 Detailed Drug Information")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if result['drug1_data']:
                        display_drug_card(result['drug1_data'], f"💊 {selected_drug1}")
                
                with col2:
                    if result['drug2_data']:
                        display_drug_card(result['drug2_data'], f"💊 {selected_drug2}")
        elif selected_drug1 or selected_drug2:
            st.info("👆 Please select both drugs to check interactions")
        else:
            st.info("👆 Select categories and drugs for both Drug 1 and Drug 2")
    
    # Tab 5: AI Drug Assistant
    with tab5:
        st.header("🤖 AI Drug Agent for 3D Printing")
        st.markdown("Ask questions about drug compatibility for **3D printing applications**. Get AI-powered answers about physical properties, chemical compatibility, routes of administration, and alternative suggestions for 3D printing.")
        
        # Initialize OpenAI client - get API key from environment variable
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        
        if not OPENAI_API_KEY:
            st.warning("⚠️ OpenAI API key not found. Please set the OPENAI_API_KEY environment variable to use the AI Drug Agent feature.")
            st.info("The AI Drug Agent tab requires an OpenAI API key. Other features will work without it.")
            st.markdown("### To use this feature:")
            st.markdown("1. Get an OpenAI API key from https://platform.openai.com/api-keys")
            st.markdown("2. Set it as an environment variable: `OPENAI_API_KEY`")
            st.markdown("3. Restart the application")
            return
        
        # Initialize session state for chat history
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        
        # Function to search drugs.com for specific drug page
        def search_drugs_com(drug_name: str, extract_dosage: bool = False) -> str:
            """Search drugs.com for drug information, optionally extract dosage"""
            try:
                # Try direct drug page first (more reliable)
                drug_name_lower = drug_name.lower().replace(' ', '-')
                direct_url = f"https://www.drugs.com/{drug_name_lower}.html"
                
                try:
                    req = urllib.request.Request(direct_url)
                    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                    with urllib.request.urlopen(req, timeout=10) as response:
                        html = response.read().decode('utf-8')
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Extract dosage information if requested
                        if extract_dosage:
                            dosage_info = []
                            
                            # Method 1: Look for anchor link to dosage section (multiple ways)
                            dosage_anchor = (soup.find('a', {'name': 'dosage'}) or 
                                           soup.find('a', {'id': 'dosage'}) or
                                           soup.find('a', href='#dosage') or
                                           soup.find(id='dosage'))
                            
                            if dosage_anchor:
                                # Get parent container if it's an anchor
                                if dosage_anchor.name == 'a':
                                    # Find the next heading or div that contains dosage content
                                    parent = dosage_anchor.parent
                                    if parent:
                                        # Get all text from parent and siblings
                                        content_parts = []
                                        # Start from the anchor's parent or next sibling
                                        current = dosage_anchor.find_next()
                                        if not current:
                                            current = parent.find_next_sibling()
                                        
                                        count = 0
                                        while current and count < 30:  # More iterations
                                            if current.name:
                                                text = current.get_text(separator='\n', strip=True)
                                                if text and len(text) > 10:
                                                    content_parts.append(text)
                                                # Stop at next major section
                                                if current.name in ['h1', 'h2']:
                                                    next_text = current.get_text().lower()
                                                    if any(word in next_text for word in ['warnings', 'precautions', 'interactions', 'side effects', 'overdose', 'contraindications']):
                                                        break
                                            current = current.find_next_sibling()
                                            count += 1
                                        
                                        if content_parts:
                                            joined_content = '\n'.join(content_parts[:4000])
                                            dosage_info.append(f"Dosage Information (from anchor):\n{joined_content}")
                                else:
                                    # It's a div or section, get its content
                                    dosage_text = dosage_anchor.get_text(separator='\n', strip=True)
                                    if dosage_text and len(dosage_text) > 50:
                                        dosage_info.append(f"Dosage Information:\n{dosage_text[:4000]}")
                            
                            # Method 2: Look for dosage section by ID or class
                            dosage_section = soup.find('div', id='dosage') or soup.find('section', id='dosage') or soup.find('div', class_='dosage')
                            if dosage_section:
                                dosage_text = dosage_section.get_text(separator='\n', strip=True)
                                if dosage_text and len(dosage_text) > 50:
                                    dosage_info.append(f"Dosage Information:\n{dosage_text[:3000]}")
                            
                            # Method 3: Look for headings with dosage/dosing
                            for heading in soup.find_all(['h2', 'h3', 'h4', 'h5']):
                                heading_text = heading.get_text().lower()
                                if 'dosage' in heading_text or 'dosing' in heading_text:
                                    # Get all content until next heading of same or higher level
                                    content_parts = []
                                    current = heading.find_next_sibling()
                                    heading_level = int(heading.name[1]) if heading.name.startswith('h') else 6
                                    
                                    while current:
                                        # Stop at next heading of same or higher level
                                        if current.name and current.name.startswith('h'):
                                            current_level = int(current.name[1]) if current.name[1].isdigit() else 6
                                            if current_level <= heading_level:
                                                break
                                        
                                        if current.name in ['p', 'div', 'ul', 'ol', 'li', 'dl', 'dt', 'dd']:
                                            text = current.get_text(separator=' ', strip=True)
                                            if text and len(text) > 20:
                                                content_parts.append(text)
                                        
                                        current = current.find_next_sibling()
                                        if len(content_parts) >= 15:  # Get more content
                                            break
                                    
                                    if content_parts:
                                        dosage_info.append(f"{heading.get_text()}:\n{' '.join(content_parts[:3000])}")
                            
                            # Method 4: Look for specific dosage patterns in the page (for structured data)
                            page_text = soup.get_text()
                            
                            # Look for "Usual Adult Dose" sections
                            usual_dose_pattern = r'Usual\s+Adult\s+Dose[:\s]+(.*?)(?=\n\n|\n[A-Z][a-z]+\s+[A-Z]|$)'
                            usual_dose_matches = re.finditer(usual_dose_pattern, page_text, re.IGNORECASE | re.DOTALL)
                            for match in usual_dose_matches:
                                dose_text = match.group(1).strip()[:1000]
                                if len(dose_text) > 50:
                                    dosage_info.append(f"Usual Adult Dose Information:\n{dose_text}")
                            
                            # Look for "Maintenance dose" which often contains frequency
                            maintenance_pattern = r'Maintenance\s+dose[:\s]+(.*?)(?=\n\n|\n[A-Z][a-z]+\s+[A-Z]|$)'
                            maintenance_matches = re.finditer(maintenance_pattern, page_text, re.IGNORECASE | re.DOTALL)
                            for match in maintenance_matches:
                                maint_text = match.group(1).strip()[:500]
                                if len(maint_text) > 30:
                                    dosage_info.append(f"Maintenance Dose Information:\n{maint_text}")
                            
                            # Also search for frequency patterns in the entire page
                            page_text = soup.get_text()
                            
                            # More comprehensive frequency patterns
                            frequency_patterns = [
                                # Numeric patterns
                                (r'(\d+)\s*(?:times?|x)\s*(?:per|a)\s*(?:day|daily)', lambda m: f"{m.group(1)} times per day"),
                                # Text patterns
                                (r'\b(once)\s+(?:daily|per day|a day)', lambda m: "once daily (1 time per day)"),
                                (r'\b(twice)\s+(?:daily|per day|a day)', lambda m: "twice daily (2 times per day)"),
                                (r'\b(three times)\s+(?:daily|per day|a day)', lambda m: "three times daily (3 times per day)"),
                                (r'\b(four times)\s+(?:daily|per day|a day)', lambda m: "four times daily (4 times per day)"),
                                # Medical abbreviations
                                (r'\b(qd|q\.?d\.?)\b', lambda m: "once daily (1 time per day)"),
                                (r'\b(bid|b\.?i\.?d\.?)\b', lambda m: "twice daily (2 times per day)"),
                                (r'\b(tid|t\.?i\.?d\.?)\b', lambda m: "three times daily (3 times per day)"),
                                (r'\b(qid|q\.?i\.?d\.?)\b', lambda m: "four times daily (4 times per day)"),
                                # Hourly patterns
                                (r'every\s+(\d+)\s+hours?', lambda m: f"every {m.group(1)} hours"),
                            ]
                            
                            found_frequencies = []
                            for pattern, formatter in frequency_patterns:
                                matches = re.finditer(pattern, page_text, re.IGNORECASE)
                                for match in matches:
                                    freq_text = formatter(match)
                                    if freq_text not in found_frequencies:
                                        found_frequencies.append(freq_text)
                            
                            # Also look for dosage instructions with frequency
                            dosage_instruction_patterns = [
                                r'(?:take|administer|dose|dosage|usual dose|recommended dose).*?(?:once|twice|three times|four times|\d+\s*(?:times?|x)).*?(?:daily|per day|a day)',
                                r'(?:initial|maintenance|loading).*?(?:dose|dosage).*?(?:once|twice|three times|four times|\d+\s*(?:times?|x)).*?(?:daily|per day)',
                                r'may be administered\s+(once|twice|three times|four times|\d+\s*times?)\s*(?:a\s+)?(?:day|daily)',
                                r'(\d+\s*mg)\s+(?:orally|orally per day)\s+(?:once|twice|three times|four times|\d+\s*times?)\s*(?:a\s+)?(?:day|daily)',
                            ]
                            
                            for pattern in dosage_instruction_patterns:
                                matches = re.finditer(pattern, page_text, re.IGNORECASE)
                                for match in matches:
                                    instruction = match.group(0)[:150]  # First 150 chars
                                    if instruction not in found_frequencies:
                                        found_frequencies.append(f"Dosage instruction: {instruction}")
                            
                            # Extract frequency from already found dosage info blocks
                            if dosage_info:
                                for info_block in dosage_info:
                                    # Look for "once a day", "twice a day", "once daily", etc. in the dosage text
                                    freq_in_text = re.findall(r'(?:may be\s+)?(?:administered\s+)?(once|twice|three times|four times|\d+\s*times?)\s*(?:a\s+)?(?:day|daily)', info_block, re.IGNORECASE)
                                    for freq_match in freq_in_text:
                                        freq_str = f"{freq_match} per day"
                                        if not any(freq_str.lower() in f.lower() for f in found_frequencies):
                                            found_frequencies.append(freq_str)
                            
                            if found_frequencies:
                                unique_freqs = list(set(found_frequencies))[:10]  # Get more results
                                dosage_info.append(f"\n🚨 DOSING FREQUENCY EXTRACTED FROM DRUGS.COM:\n" + "\n".join([f"  • {freq}" for freq in unique_freqs]))
                            
                            # Also look for specific dosage text patterns
                            dosage_text_patterns = [
                                r'(?:take|administer|dose|dosage).*?(?:once|twice|three times|four times|\d+\s*(?:times?|x)).*?(?:daily|per day|a day)',
                                r'(?:usual|recommended|standard).*?(?:dose|dosage).*?(?:once|twice|three times|four times|\d+\s*(?:times?|x)).*?(?:daily|per day)',
                            ]
                            
                            for pattern in dosage_text_patterns:
                                matches = re.findall(pattern, page_text, re.IGNORECASE)
                                if matches:
                                    dosage_info.append(f"\nDosage instructions found: {matches[0][:200]}")
                                    break
                            
                            if dosage_info:
                                return "\n\n".join(dosage_info)
                            
                            # If no specific dosage section, get general content that might contain dosage
                            main_content = soup.find('div', class_='contentBox') or soup.find('article') or soup.find('main')
                            if main_content:
                                content_text = main_content.get_text(separator='\n', strip=True)
                                # Look for dosage-related paragraphs
                                paragraphs = content_text.split('\n')
                                dosage_paragraphs = []
                                for para in paragraphs:
                                    if any(word in para.lower() for word in ['dosage', 'dosing', 'frequency', 'times per day', 'times/day', 'daily']):
                                        if len(para) > 30:
                                            dosage_paragraphs.append(para[:500])
                                if dosage_paragraphs:
                                    return "Dosage Information from page content:\n" + "\n".join(dosage_paragraphs[:5])
                        
                        # Extract general information
                        results = []
                        # Look for main content
                        main_content = soup.find('div', class_='contentBox') or soup.find('article') or soup.find('main')
                        if main_content:
                            # Get text from main content
                            text = main_content.get_text(separator='\n', strip=True)
                            if text and len(text) > 100:
                                results.append(text[:1500])
                        
                        if results:
                            return "\n\n".join(results)
                except:
                    pass  # Fall back to search
                
                # Fallback to search
                search_url = f"https://www.drugs.com/search.php?searchterm={urllib.parse.quote(drug_name)}"
                req = urllib.request.Request(search_url)
                req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    html = response.read().decode('utf-8')
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract relevant information
                    results = []
                    content_divs = soup.find_all('div', class_=['contentBox', 'ddc-content'])
                    for div in content_divs[:3]:
                        text = div.get_text(strip=True)
                        if text and len(text) > 50:
                            results.append(text[:500])
                    
                    if results:
                        return "\n\n".join(results)
                    return f"Found search results for {drug_name} on drugs.com, but specific content extraction needs refinement."
            except Exception as e:
                return f"Error searching drugs.com: {str(e)}"
        
        # Function to get drug alternatives from same category
        def get_alternatives_from_category(drug_name: str, db: ComprehensiveDrugQuery) -> List[str]:
            """Get alternative drugs from the same category"""
            drug = db.find_drug(drug_name)
            if not drug:
                return []
            
            categories = drug.get('categories', [])
            if not categories:
                return []
            
            # Get first valid category name
            first_category = ''
            for entry in categories:
                first_category = db._normalize_category_name(entry)
                if first_category:
                    break
            
            if not first_category:
                return []
            
            # Get all drugs in this category
            alternatives = db.get_drugs_by_category(first_category)
            # Remove the current drug
            alternatives = [a for a in alternatives if a.lower() != drug_name.lower()]
            return alternatives[:10]  # Return top 10 alternatives
        
        # Function to process AI query
        def process_ai_query(query: str, db: ComprehensiveDrugQuery) -> str:
            """Process user query with AI and database"""
            # Extract drug names from query
            drug_names = []
            query_lower = query.lower()
            
            # Common drug category mappings
            category_mappings = {
                'nsaid': ['ibuprofen', 'aspirin', 'naproxen', 'diclofenac', 'indomethacin'],
                'nsaids': ['ibuprofen', 'aspirin', 'naproxen', 'diclofenac', 'indomethacin'],
                'ace inhibitor': ['lisinopril', 'enalapril', 'captopril', 'ramipril'],
                'ace inhibitors': ['lisinopril', 'enalapril', 'captopril', 'ramipril'],
                'beta blocker': ['metoprolol', 'atenolol', 'propranolol'],
                'beta blockers': ['metoprolol', 'atenolol', 'propranolol'],
            }
            
            # Check for category mentions first
            for category, drugs in category_mappings.items():
                if category in query_lower:
                    # Add representative drugs from category
                    for cat_drug in drugs[:2]:  # Take first 2 as examples
                        drug_names.append(cat_drug.title())
            
            # Try to find specific drug names in query (search all drugs, prioritize exact matches)
            exact_matches = []
            partial_matches = []
            
            # Split query into words and check each
            query_words = query_lower.split()
            
            for drug in db.drugs:
                drug_name = drug.get('name', '')
                if not drug_name:
                    continue
                drug_name_lower = drug_name.lower()
                
                # Check for exact word match (whole word, case-insensitive)
                for word in query_words:
                    # Remove punctuation for better matching
                    clean_word = word.strip('.,!?;:()[]{}')
                    if clean_word == drug_name_lower:
                        if drug_name not in exact_matches and drug_name not in drug_names:
                            exact_matches.append(drug_name)
                
                # Check if drug name appears as a whole in query (for multi-word drug names)
                if drug_name_lower in query_lower:
                    # Make sure it's not already added
                    if drug_name not in exact_matches and drug_name not in drug_names:
                        # Check if it's a meaningful match (not just a substring)
                        words_in_drug = drug_name_lower.split()
                        if len(words_in_drug) == 1 or all(w in query_lower for w in words_in_drug):
                            exact_matches.append(drug_name)
            
            # Use exact matches first, then category drugs (limit to 3 drugs total)
            drug_names = (exact_matches + drug_names)[:3]
            
            # If still no matches, try fuzzy matching for common drugs
            if not drug_names:
                common_drugs = ['lisinopril', 'aspirin', 'ibuprofen', 'metformin', 'warfarin', 'losartan', 'atorvastatin']
                for common_drug in common_drugs:
                    if common_drug in query_lower:
                        # Find the actual drug name in database
                        for drug in db.drugs:
                            if drug.get('name', '').lower() == common_drug:
                                drug_names.append(drug.get('name'))
                                break
                        if len(drug_names) >= 2:
                            break
            
            # First, check which drugs need external dosage search
            missing_dosage_drugs = []
            for drug_name in drug_names:
                summary = db.get_summary(drug_name)
                if 'error' not in summary:
                    dosing = summary.get('dosing', {})
                    frequency = dosing.get('frequency')
                    times_per_day = dosing.get('times_per_day')
                    if not frequency and not times_per_day:
                        missing_dosage_drugs.append(drug_name)
            
            # Search drugs.com for missing dosage information (do this early)
            external_info = ""
            if missing_dosage_drugs:
                dosage_info_list = []
                frequency_summary = []
                
                for drug_name in missing_dosage_drugs:
                    dosage_info = search_drugs_com(drug_name, extract_dosage=True)
                    if dosage_info and 'Error' not in dosage_info:
                        # Extract frequency from the dosage info if present (check both old and new formats)
                        freq_match = re.search(r'DOSING FREQUENCY EXTRACTED(?: FROM DRUGS\.COM)?:\s*(.+?)(?:\n|$)', dosage_info, re.IGNORECASE | re.DOTALL)
                        if not freq_match:
                            # Try to find frequency in bullet points
                            freq_match = re.search(r'🚨 DOSING FREQUENCY EXTRACTED FROM DRUGS\.COM:\s*(.+?)(?:\n\n|\n===|$)', dosage_info, re.IGNORECASE | re.DOTALL)
                        
                        if freq_match:
                            freq_text = freq_match.group(1).strip()
                            # Clean up the frequency text
                            freq_text = re.sub(r'\s+', ' ', freq_text)  # Normalize whitespace
                            frequency_summary.append(f"{drug_name}: {freq_text[:200]}")  # Limit length
                        else:
                            # Try to extract any frequency pattern from the text
                            freq_patterns = [
                                r'(\d+\s*times?\s*per\s*day)',
                                r'(once|twice|three times|four times)\s*daily',
                                r'\b(bid|tid|qid|qd)\b',
                            ]
                            for pattern in freq_patterns:
                                match = re.search(pattern, dosage_info, re.IGNORECASE)
                                if match:
                                    frequency_summary.append(f"{drug_name}: {match.group(0)}")
                                    break
                        
                        dosage_info_list.append(f"=== {drug_name.upper()} DOSAGE FROM DRUGS.COM ===\n{dosage_info}\n")
                
                if dosage_info_list:
                    summary_text = ""
                    if frequency_summary:
                        summary_text = f"\n📊 QUICK SUMMARY - DOSING FREQUENCIES FOUND:\n" + "\n".join([f"  • {freq}" for freq in frequency_summary]) + "\n"
                    
                    external_info = f"\n\n{'='*60}\nEXTERNAL DOSAGE INFORMATION FROM DRUGS.COM (AUTOMATICALLY SEARCHED DUE TO MISSING DATA IN DATABASE):\n{'='*60}{summary_text}\n" + "\n".join(dosage_info_list)
            
            # Build context from database (now we can use external_info)
            context = "Drug Database Information for 3D Printing Assessment:\n"
            
            if drug_names:
                for drug_name in drug_names[:3]:  # Limit to 3 drugs
                    summary = db.get_summary(drug_name)
                    if 'error' not in summary:
                        context += f"\n{drug_name}:\n"
                        context += f"- Type: {summary.get('type', 'Unknown')} (Note: Biologics cannot be 3D printed with standard methods)\n"
                        context += f"- Interactions: {summary.get('interaction_count', 0)} known interactions\n"
                        
                        # Physical properties for 3D printing
                        properties = summary.get('properties', {})
                        if properties:
                            context += f"- Physical Properties (for 3D printing):\n"
                            if properties.get('Melting Point'):
                                context += f"  * Melting Point: {properties['Melting Point']}\n"
                            if properties.get('Molecular Weight'):
                                context += f"  * Molecular Weight: {properties['Molecular Weight']}\n"
                            if properties.get('Water Solubility'):
                                context += f"  * Water Solubility: {properties['Water Solubility']}\n"
                            if properties.get('logP'):
                                context += f"  * logP: {properties['logP']}\n"
                        
                        dosing = summary.get('dosing', {})
                        frequency = dosing.get('frequency')
                        times_per_day = dosing.get('times_per_day')
                        
                        # Check if we have external dosage for this drug
                        if drug_name in missing_dosage_drugs and external_info:
                            # Extract external dosage for this specific drug
                            drug_section = re.search(rf'=== {drug_name.upper()} DOSAGE FROM DRUGS\.COM ===\s*(.+?)(?:\n===|$)', external_info, re.IGNORECASE | re.DOTALL)
                            if drug_section:
                                # Extract frequency from external info
                                freq_extracted = re.search(r'🚨 DOSING FREQUENCY EXTRACTED FROM DRUGS\.COM:\s*(.+?)(?:\n\n|\n===|$)', drug_section.group(1), re.IGNORECASE | re.DOTALL)
                                if freq_extracted:
                                    external_freq = freq_extracted.group(1).strip()[:200]
                                    context += f"- 🚨 DOSING FREQUENCY (FROM DRUGS.COM): {external_freq}\n"
                                    context += f"  ⚠️ IMPORTANT: This frequency was found from drugs.com - you MUST mention it in your answer!\n"
                                else:
                                    # Try to find any frequency pattern
                                    freq_pattern = re.search(r'(\d+\s*times?\s*per\s*day|once|twice|three times|four times)\s*(?:daily|per day)', drug_section.group(1), re.IGNORECASE)
                                    if freq_pattern:
                                        context += f"- 🚨 DOSING FREQUENCY (FROM DRUGS.COM): {freq_pattern.group(0)}\n"
                                        context += f"  ⚠️ IMPORTANT: This frequency was found from drugs.com - you MUST mention it in your answer!\n"
                        elif frequency or times_per_day:
                            context += f"- Dosing Frequency: {frequency or times_per_day} (from database)\n"
                        else:
                            context += f"- Dosing Frequency: Not available in database\n"
                        
                        routes = dosing.get('routes', [])
                        if routes and isinstance(routes, list):
                            context += f"- Routes of Administration: {', '.join(str(r) for r in routes[:3])} (for 3D printing delivery systems)\n"
                        elif routes:
                            context += f"- Routes of Administration: {routes} (for 3D printing delivery systems)\n"
                        else:
                            context += f"- Routes of Administration: Unknown\n"
            
            # Check if compatibility question
            if len(drug_names) >= 2:
                result = db.check_compatibility(drug_names[0], drug_names[1])
                context += f"\n\nCompatibility Check Results for {drug_names[0]} + {drug_names[1]}:\n"
                context += f"- Compatibility Status: {'NOT COMPATIBLE - Issues Found' if not result.get('compatible', True) else 'No major incompatibilities detected'}\n"
                
                # Detailed interaction information
                interactions = result.get('interactions', [])
                if interactions:
                    context += f"- Number of Interactions Found: {len(interactions)}\n"
                    severe_interactions = [i for i in interactions if i.get('severity') == 'severe']
                    moderate_interactions = [i for i in interactions if i.get('severity') == 'moderate']
                    if severe_interactions:
                        context += f"- SEVERE Interactions: {len(severe_interactions)}\n"
                        for inter in severe_interactions[:2]:
                            context += f"  * {inter.get('drug', 'Unknown')}: {inter.get('description', '')[:200]}\n"
                    if moderate_interactions:
                        context += f"- MODERATE Interactions: {len(moderate_interactions)}\n"
                        for inter in moderate_interactions[:2]:
                            context += f"  * {inter.get('drug', 'Unknown')}: {inter.get('description', '')[:200]}\n"
                else:
                    context += f"- Interactions: No known interactions detected\n"
                
                if result.get('issues'):
                    context += f"- Critical Issues: {len(result['issues'])} found\n"
                    for issue in result['issues'][:3]:
                        context += f"  * {issue}\n"
                if result.get('warnings'):
                    context += f"- Warnings: {len(result['warnings'])} found\n"
                    for warning in result['warnings'][:3]:
                        context += f"  * {warning}\n"
                if result.get('routes', {}).get('common'):
                    context += f"- Common Routes: {', '.join(result['routes']['common'][:3])}\n"
            
            # Check if asking for alternatives
            alternatives_info = ""
            if any(word in query_lower for word in ['alternative', 'substitute', 'replace', 'instead', 'more compatible']):
                if drug_names:
                    original_drug = drug_names[0]
                    alternatives = get_alternatives_from_category(original_drug, db)
                    if alternatives:
                        alternatives_info = f"\n\nAlternative drugs in same category as {original_drug}: {', '.join(alternatives[:5])}\n"
                        # Check interactions for top alternatives
                        alternatives_with_interactions = []
                        for alt_drug in alternatives[:5]:
                            alt_result = db.check_compatibility(original_drug, alt_drug)
                            alt_interactions = alt_result.get('interactions', [])
                            if alt_interactions:
                                alternatives_with_interactions.append(f"{alt_drug} (has {len(alt_interactions)} interaction(s))")
                            else:
                                alternatives_with_interactions.append(f"{alt_drug} (no known interactions)")
                        if alternatives_with_interactions:
                            alternatives_info += f"Interaction check with {original_drug}:\n"
                            for alt_info in alternatives_with_interactions[:5]:
                                alternatives_info += f"  - {alt_info}\n"
            
            # external_info is now created earlier, before building context
            
            # Also search if explicitly requested
            if any(word in query_lower for word in ['drugs.com', 'external', 'online', 'web', 'search']):
                if drug_names:
                    general_info = search_drugs_com(drug_names[0], extract_dosage=False)
                    if general_info:
                        external_info += f"\n\nAdditional External Information from drugs.com:\n{general_info}"
            
            # Build prompt for OpenAI
            system_prompt = """You are a drug compatibility assistant for 3D PRINTING applications. You help assess whether drugs can be 3D printed together based on their physical, chemical, and pharmaceutical properties.

Your focus is on 3D PRINTING COMPATIBILITY, not patient medication use. Consider:
- Physical properties (melting point, solubility, molecular weight)
- Chemical compatibility for 3D printing processes
- Routes of administration compatibility
- Dosing frequency compatibility (for timed-release formulations)
- Drug type (small molecule vs biologic - biologics cannot be 3D printed with standard methods)
- Drug-drug interactions (which may affect chemical stability in 3D printing)

IMPORTANT GUIDELINES:
1. Focus on 3D PRINTING compatibility, not patient safety
2. Present facts from the database about physical/chemical properties
3. If interactions are found, explain how they might affect 3D printing compatibility
4. Mention if drugs are biologics (cannot be 3D printed with standard methods)
5. Discuss routes of administration in context of 3D printing delivery systems
6. Use phrases like "For 3D printing purposes..." or "From a 3D printing perspective..."
7. Do NOT provide medical advice for patients - this is for 3D printing assessment only

CRITICAL DOSAGE INFORMATION RULE:
- If dosing frequency information is missing from the database for any drug, the system will automatically search drugs.com
- When external dosage information from drugs.com is provided in the context, you MUST:
  1. Extract the dosing frequency from that information
  2. Clearly state it in your answer using the format: "According to drugs.com, [drug name] is typically dosed [frequency/times per day]"
  3. DO NOT say "dosing frequency is not available" if external information is provided
  4. Present this information prominently in your answer, not as a footnote

Use the provided database context to answer questions accurately. External dosage information from drugs.com will be automatically provided when database information is missing - you must use it."""
            
            # Build a clear summary of what was found
            dosage_status = []
            for drug_name in drug_names:
                summary = db.get_summary(drug_name)
                if 'error' not in summary:
                    dosing = summary.get('dosing', {})
                    frequency = dosing.get('frequency')
                    times_per_day = dosing.get('times_per_day')
                    if frequency or times_per_day:
                        dosage_status.append(f"{drug_name}: HAS dosing frequency in database ({frequency or times_per_day})")
                    else:
                        dosage_status.append(f"{drug_name}: MISSING dosing frequency in database - external search was performed")
            
            # Check if external info was actually found
            has_external_dosage = bool(external_info and 'EXTERNAL DOSAGE INFORMATION' in external_info)
            external_dosage_drugs = []
            if has_external_dosage:
                # Extract drug names from external info
                for drug_name in missing_dosage_drugs:
                    if drug_name.upper() in external_info:
                        external_dosage_drugs.append(drug_name)
            
            user_prompt = f"""User Question: {query}

{'='*80}
🚨 MANDATORY: READ THIS FIRST - DOSAGE INFORMATION CHECK
{'='*80}

STEP 1: Check DOSAGE STATUS below:
{chr(10).join(dosage_status) if dosage_status else 'No drugs identified'}

STEP 2: Check if EXTERNAL DOSAGE INFORMATION exists:
- External dosage search performed: {'YES' if has_external_dosage else 'NO'}
- Drugs with external dosage found: {', '.join(external_dosage_drugs) if external_dosage_drugs else 'None'}

STEP 3: If external dosage exists (you see "EXTERNAL DOSAGE INFORMATION FROM DRUGS.COM" below), you MUST:
- Extract the dosing frequency from that section
- State it clearly: "According to drugs.com, [drug name] is typically dosed [frequency/times per day]"
- DO NOT say "dosing frequency is not available" or "not available in the database" if external info exists
- Look for "DOSING FREQUENCY EXTRACTED" or "QUICK SUMMARY" sections - those contain the frequency

{'='*80}
DRUG DATABASE INFORMATION:
{'='*80}
Drugs identified in the query: {', '.join(drug_names) if drug_names else 'None found - please search database'}

{context}{alternatives_info}

{'='*80}
EXTERNAL DOSAGE INFORMATION FROM DRUGS.COM (IF AVAILABLE):
{'='*80}
{external_info if external_info else 'No external dosage information was needed or found. All drugs have dosing data in the database.'}
{'='*80}

CRITICAL INSTRUCTIONS FOR 3D PRINTING ASSESSMENT:
- You MUST answer about the drugs the user actually asked about: {query}
- If drugs were identified ({', '.join(drug_names) if drug_names else 'none'}), use ONLY those drugs in your answer
- If no drugs were identified, clearly state that and ask the user to specify drug names
- Do NOT mention drugs that were not in the user's question
- This is for 3D PRINTING compatibility assessment, NOT patient medication advice
- Focus on physical/chemical properties relevant to 3D printing
- If interactions are found, explain how they might affect 3D printing (chemical stability, incompatibility, etc.)
- If drugs are biologics, state they cannot be 3D printed with standard methods
- Discuss routes of administration in context of 3D printing delivery systems

**🚨 ABSOLUTELY CRITICAL - DOSAGE INFORMATION (READ THIS CAREFULLY):**

AUTOMATIC DRUGS.COM SEARCH RULE:
- The system automatically searches drugs.com for dosage information when it's missing from the database
- When external dosage is found, it will be provided in the context below
- You MUST extract and use this information in your answer

CHECK THE DRUG DATABASE INFORMATION SECTION ABOVE FIRST:
- If you see "🚨 DOSING FREQUENCY (FROM DRUGS.COM)" for any drug, that means external dosage WAS FOUND
- You MUST include this frequency in your answer using the exact format: "According to drugs.com, [drug name] is typically dosed [frequency]"
- DO NOT say "dosing frequency is not available" or "not available in the database" if you see "🚨 DOSING FREQUENCY (FROM DRUGS.COM)"
- This information should be stated prominently in your answer, not hidden or mentioned as a footnote

ALSO CHECK THE EXTERNAL DOSAGE SECTION BELOW:
1. If you see "EXTERNAL DOSAGE INFORMATION FROM DRUGS.COM" section with content, that means dosage WAS FOUND via automatic search
2. You MUST extract and state the dosing frequency from that section
3. DO NOT say "dosing frequency is not available" or "not available in the database" if external info exists
4. Look for patterns like "once daily", "twice daily", "3 times per day", "BID", "TID" in the external info
5. Format: "According to drugs.com, [drug name] is typically dosed [frequency/times per day]"
6. If you see "QUICK SUMMARY - DOSING FREQUENCIES FOUND" or "🚨 DOSING FREQUENCY EXTRACTED", that IS the frequency - use it!
7. ONLY if BOTH the drug context shows "Not available in database" AND the external info section is empty can you say dosing frequency is not available

MANDATORY REQUIREMENTS:
- For any drug that shows "🚨 DOSING FREQUENCY (FROM DRUGS.COM)" in the drug context above, you MUST state it in your answer. This is not optional.
- The dosage frequency from drugs.com should be presented as a fact in your answer, not as "if available" or "may be"
- Example: "According to drugs.com, Amiodarone is typically dosed [frequency]" - state this clearly and prominently

Do NOT provide medical advice - focus on 3D printing technical assessment

Please provide a comprehensive answer focused on 3D printing compatibility for the SPECIFIC DRUGS mentioned in the user's question. If external dosage information is provided, you MUST extract and clearly state the dosing frequency - do NOT say it's missing."""
            
            try:
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )
                return response.choices[0].message.content
            except Exception as e:
                return f"Error processing query with AI: {str(e)}. Please try again or use the other tabs for direct database queries."
        
        # Display chat interface
        st.markdown("### 💬 Ask Your Question")
        
        # Display chat history
        for i, (role, message) in enumerate(st.session_state.chat_history):
            if role == "user":
                with st.chat_message("user"):
                    st.write(message)
            else:
                with st.chat_message("assistant"):
                    st.write(message)
        
        # Input for new question
        user_query = st.text_input(
            "Enter your question about drug compatibility for 3D printing:",
            key="ai_query_input",
            placeholder="e.g., 'Are Lisinopril and Losartan compatible for 3D printing?', 'What are alternatives to Metformin for 3D printing?', 'Can Aspirin and Ibuprofen be 3D printed together?'"
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            ask_button = st.button("Ask", type="primary", use_container_width=True)
        
        with col2:
            if st.button("Clear Chat", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
        
        # Process query
        if ask_button and user_query:
            with st.spinner("🤖 AI is thinking..."):
                # Add user message to history
                st.session_state.chat_history.append(("user", user_query))
                
                # Get AI response
                ai_response = process_ai_query(user_query, db)
                
                # Add AI response to history
                st.session_state.chat_history.append(("assistant", ai_response))
                
                # Rerun to display new messages
                st.rerun()
        
        # Show example questions
        with st.expander("💡 Example Questions for 3D Printing"):
            st.markdown("""
            **3D Printing Compatibility Questions:**
            - "Are Lisinopril and Losartan compatible for 3D printing?"
            - "Can Aspirin and Ibuprofen be 3D printed together?"
            - "What are the chemical interactions between Metformin and Warfarin for 3D printing?"
            
            **Alternative Drug Questions:**
            - "What are alternatives to Metformin for 3D printing?"
            - "Give me substitutes for Lisinopril that can be 3D printed"
            - "What drugs can replace Aspirin in a 3D printed formulation?"
            
            **Physical/Chemical Property Questions:**
            - "What are the physical properties of Aspirin for 3D printing?"
            - "What is the melting point of Lisinopril?"
            - "What routes of administration are compatible for 3D printing Metformin?"
            
            **External Search:**
            - "Search drugs.com for physical properties of [drug name]"
            """)
        
        # Show database stats
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🤖 AI Assistant Info")
        st.sidebar.info(f"Database: {len(db.drugs):,} drugs available\n\nAsk questions about:\n- 3D printing compatibility\n- Physical/chemical properties\n- Routes for 3D printing\n- Alternative drugs\n- Drug interactions (for 3D printing)")


if __name__ == "__main__":
    main()

