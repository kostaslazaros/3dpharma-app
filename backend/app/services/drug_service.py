"""
Drug Service - Core business logic for drug queries

Memory-optimized: builds a compact index in memory (~30MB) and streams
full drug records from disk on demand. Keeps well within 512MB free tier limits.
"""

import os
import re
import json
import threading
from typing import Dict, List, Optional, Any

try:
    import ijson
    IJSON_AVAILABLE = True
except ImportError:
    IJSON_AVAILABLE = False

from bs4 import BeautifulSoup

from app.services.severity_classifier import classify_severity_simple, get_severity_emoji


import tempfile
import platform

# Use platform-appropriate temp directory
if platform.system() == 'Windows':
    DB_CACHE_PATH = os.path.join(tempfile.gettempdir(), 'drug_database.json')
else:
    DB_CACHE_PATH = '/tmp/drug_database.json'
FULL_DRUG_CACHE_SIZE = 30  # max full drug records kept in memory at once


# openFDA label sections retained for the co-administration / contraindication checker.
_OPENFDA_LABEL_SECTION_FIELDS = [
    'boxed_warning', 'contraindications', 'warnings', 'warnings_and_cautions',
    'drug_interactions', 'use_in_specific_populations', 'pregnancy',
    'pregnancy_or_breast_feeding', 'nursing_mothers', 'pediatric_use',
    'geriatric_use', 'adverse_reactions', 'do_not_use', 'ask_doctor',
    'ask_doctor_or_pharmacist', 'stop_use', 'when_using',
]
_MAX_SECTION_CHARS = 4000


def _openfda_section_text(value) -> str:
    """openFDA sections are usually a list of strings; join and truncate."""
    if isinstance(value, list):
        text = ' '.join(str(v).strip() for v in value if v)
    elif isinstance(value, str):
        text = value.strip()
    else:
        text = ''
    return text[:_MAX_SECTION_CHARS]


def normalize_route(route: str) -> str:
    """Normalize route names to consistent title case."""
    if not route:
        return route
    if route.isupper():
        route = route.title()
    route = route.replace('ORAL', 'Oral').replace('oral', 'Oral')
    route = route.replace('(INHALATION)', '(inhalation)')
    return route


class DrugService:
    """Query interface for comprehensive database with OpenFDA fallback"""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    GDRIVE_FILE_ID = '12o_cdObA01lxXJMY8LjCqlPVrXF56bZF'
    GDRIVE_URL = f'https://drive.google.com/uc?export=download&id={GDRIVE_FILE_ID}'

    def __init__(
        self,
        db_file: str = 'comprehensive_drug_database_compact.json',
        openfda_file: str = 'OpenFDAfull.json',
    ):
        if DrugService._initialized:
            return

        # --- Compact in-memory index (all drugs, minimal fields) ---
        self.compact_drugs: List[Dict] = []
        self.name_to_idx: Dict[str, int] = {}
        self.id_to_idx: Dict[str, int] = {}
        self.metadata: Dict = {}

        # --- Full drug LRU cache ---
        self._full_cache: Dict[str, Dict] = {}
        self._cache_order: List[str] = []
        self._cache_lock = threading.Lock()

        # --- Path to full JSON on disk ---
        self._db_path: Optional[str] = None

        # --- OpenFDA lightweight data ---
        self.openfda_drugs: Dict = {}
        self.openfda_name_index: Dict = {}

        # --- Condition labels (openFDA label sections for contraindications) ---
        self.condition_labels: Dict = {}
        self.condition_label_index: Dict = {}

        print("Initializing drug database...")

        self._db_path = self._get_db_path(db_file)

        if self._db_path:
            self._build_compact_index()
        else:
            print("Warning: No database available. Using empty database.")

        print(f"Database loaded: {len(self.compact_drugs)} drugs")

        openfda_enabled = os.getenv('ENABLE_OPENFDA_DATA', 'true').lower() not in ('0', 'false', 'no')
        if openfda_enabled and IJSON_AVAILABLE:
            self._load_openfda_data(openfda_file)

        self._load_condition_labels()

        DrugService._initialized = True

    # ------------------------------------------------------------------
    # Database acquisition
    # ------------------------------------------------------------------

    def _get_db_path(self, db_file: str) -> Optional[str]:
        """Find database file locally, in cache, or download it."""
        local_paths = [
            db_file,
            os.path.join('data', db_file),
            os.path.join('..', 'drug-app', db_file),
            os.path.join('..', 'data', db_file),
            'comprehensive_drug_database.json',
            os.path.join('data', 'comprehensive_drug_database.json'),
        ]
        for path in local_paths:
            if os.path.exists(path):
                print(f"Found local database: {path}")
                return path

        if os.path.exists(DB_CACHE_PATH) and os.path.getsize(DB_CACHE_PATH) > 10_000_000:
            print(f"Using cached database: {DB_CACHE_PATH}")
            return DB_CACHE_PATH

        print("No local database found. Downloading from Google Drive...")
        return self._download_to_disk(DB_CACHE_PATH)

    def _download_to_disk(self, dest_path: str) -> Optional[str]:
        # Downloads the 200MB file to /tmp/ on Render's server using streaming chunks, never loading it all into memory at once
        """Stream-download database to disk. Never holds full file in RAM."""
        try:
            import httpx
        except ImportError:
            print("Warning: httpx not installed. Cannot download database.")
            return None

        print("Connecting to Google Drive database...")
        print("Downloading ~200MB file to disk (this may take a minute)...")

        try:
            with httpx.Client(follow_redirects=True, timeout=300.0) as client:
                download_url = f"{self.GDRIVE_URL}&confirm=t"

                # Probe first to detect HTML confirmation pages
                probe = client.get(download_url)
                content_start = probe.content[:2000]

                if b'"drugs"' not in content_start and (
                    b'<html' in content_start
                    or b'<!DOCTYPE' in content_start
                    or len(probe.content) < 1_000_000
                ):
                    uuid_match = re.search(r'uuid=([^&"\']+)', probe.text)
                    confirm_match = re.search(r'confirm=([^&"\']+)', probe.text)

                    if uuid_match:
                        download_url = (
                            f"https://drive.usercontent.google.com/download"
                            f"?id={self.GDRIVE_FILE_ID}&export=download&confirm=t"
                            f"&uuid={uuid_match.group(1)}"
                        )
                    elif confirm_match and confirm_match.group(1) != 't':
                        download_url = f"{self.GDRIVE_URL}&confirm={confirm_match.group(1)}"
                    else:
                        download_url = (
                            f"https://drive.usercontent.google.com/download"
                            f"?id={self.GDRIVE_FILE_ID}&export=download&confirm=t"
                        )

                    # Stream to disk
                    with client.stream('GET', download_url) as stream_resp:
                        with open(dest_path, 'wb') as f:
                            for chunk in stream_resp.iter_bytes(chunk_size=65536):
                                f.write(chunk)
                else:
                    # probe already got the file content (small enough)
                    with open(dest_path, 'wb') as f:
                        f.write(probe.content)

                size_mb = os.path.getsize(dest_path) / 1_000_000
                print(f"Downloaded {size_mb:.1f}MB to {dest_path}")
                return dest_path

        except Exception as e:
            print(f"Failed to download database: {e}")
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
            return None

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def _build_compact_index(self) -> None:
        # on startup, streams through the JSON with ijson and only saves names, IDs, categories into RAM 
        """Stream-parse database file to build minimal in-memory index."""
        if not IJSON_AVAILABLE:
            print("ijson not available — falling back to full load (may OOM on small instances)")
            self._fallback_full_load()
            return

        print("Stream-parsing database to build compact index...")
        count = 0

        try:
            with open(self._db_path, 'rb') as f:
                for drug in ijson.items(f, 'drugs.item'):
                    name = drug.get('name', '')
                    if not name:
                        continue

                    drugbank_ids = drug.get('drugbank_ids') or {}
                    primary_id = drugbank_ids.get('primary', '')
                    secondary_ids = drugbank_ids.get('secondary', []) or []

                    categories = []
                    for cat in drug.get('categories', []):
                        cat_name = self._normalize_category_name(cat)
                        if cat_name:
                            categories.append(cat_name)

                    interaction_ids: set = set()
                    for interaction in drug.get('drug_interactions', []):
                        int_id = interaction.get('drugbank_id')
                        if int_id:
                            interaction_ids.add(int_id)

                    idx = len(self.compact_drugs)
                    entry = {
                        'name': name,
                        'name_lower': name.lower(),
                        # Keep drugbank_ids in original format for router compatibility
                        'drugbank_ids': {'primary': primary_id, 'secondary': secondary_ids},
                        'type': drug.get('type', ''),
                        'groups': drug.get('groups', []),
                        'categories': categories,
                        '_interaction_ids': interaction_ids,
                        '_has_dosing': bool(
                            (drug.get('dosing_info') or {}).get('has_dosing', False)
                            or drug.get('dosages')
                        ),
                    }

                    self.compact_drugs.append(entry)
                    self.name_to_idx[name.lower()] = idx
                    if primary_id:
                        self.id_to_idx[primary_id] = idx
                    for sid in secondary_ids:
                        if sid and sid not in self.id_to_idx:
                            self.id_to_idx[sid] = idx

                    count += 1

            # Try to get metadata
            try:
                with open(self._db_path, 'rb') as f:
                    self.metadata = next(ijson.items(f, 'metadata'))
            except Exception:
                pass

            self.metadata['total_drugs'] = count
            self.metadata['drugs_with_dosing'] = sum(
                1 for d in self.compact_drugs if d.get('_has_dosing')
            )
            print(f"Compact index built: {count} drugs")

        except Exception as e:
            print(f"Stream parsing failed ({e}). Trying fallback...")
            self._fallback_full_load()

    def _fallback_full_load(self) -> None:
        """Last-resort: load full JSON. May OOM on 512MB instances."""
        try:
            with open(self._db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.metadata = data.get('metadata', {})
            for i, drug in enumerate(data.get('drugs', [])):
                name = drug.get('name', '')
                if not name:
                    continue
                drugbank_ids = drug.get('drugbank_ids') or {}
                primary_id = drugbank_ids.get('primary', '')
                secondary_ids = drugbank_ids.get('secondary', []) or []
                categories = []
                for cat in drug.get('categories', []):
                    cat_name = self._normalize_category_name(cat)
                    if cat_name:
                        categories.append(cat_name)
                interaction_ids: set = set()
                for interaction in drug.get('drug_interactions', []):
                    int_id = interaction.get('drugbank_id')
                    if int_id:
                        interaction_ids.add(int_id)

                idx = len(self.compact_drugs)
                entry = {
                    'name': name,
                    'name_lower': name.lower(),
                    'drugbank_ids': {'primary': primary_id, 'secondary': secondary_ids},
                    'type': drug.get('type', ''),
                    'groups': drug.get('groups', []),
                    'categories': categories,
                    '_interaction_ids': interaction_ids,
                    '_has_dosing': bool(
                        (drug.get('dosing_info') or {}).get('has_dosing', False)
                        or drug.get('dosages')
                    ),
                }
                self.compact_drugs.append(entry)
                self.name_to_idx[name.lower()] = idx
                if primary_id:
                    self.id_to_idx[primary_id] = idx
        except Exception as e:
            print(f"Fallback load also failed: {e}")

    # ------------------------------------------------------------------
    # Full drug loading (on-demand, cached)
    # ------------------------------------------------------------------

    def _get_full_drug(self, drug_name: str) -> Optional[Dict]:
        #  specific drug's details --> streams the file from disk to find just that one drug, then caches it
        """
        Stream the database file to find one drug's complete record.
        Results are cached (LRU, up to FULL_DRUG_CACHE_SIZE entries).
        """
        cache_key = drug_name.lower()

        with self._cache_lock:
            if cache_key in self._full_cache:
                return self._full_cache[cache_key]

        if not self._db_path or not IJSON_AVAILABLE:
            return None

        name_lower = drug_name.lower()
        found = None
        try:
            with open(self._db_path, 'rb') as f:
                for drug in ijson.items(f, 'drugs.item'):
                    if drug.get('name', '').lower() == name_lower:
                        found = drug
                        break
        except Exception as e:
            print(f"Error loading full drug '{drug_name}': {e}")
            return None

        if found:
            with self._cache_lock:
                if len(self._full_cache) >= FULL_DRUG_CACHE_SIZE:
                    oldest = self._cache_order.pop(0)
                    self._full_cache.pop(oldest, None)
                self._full_cache[cache_key] = found
                self._cache_order.append(cache_key)

        return found

    # ------------------------------------------------------------------
    # OpenFDA data (unchanged — already lightweight)
    # ------------------------------------------------------------------

    def _load_openfda_data(self, openfda_file: str) -> None:
        openfda_paths = [
            openfda_file,
            os.path.join('data', openfda_file),
            os.path.join('..', 'drug-app', openfda_file),
        ]
        actual_path = None
        for path in openfda_paths:
            if os.path.exists(path):
                actual_path = path
                break
        if not actual_path:
            return
        try:
            with open(actual_path, 'rb') as f:
                for drug_id, raw_entry in ijson.kvitems(f, 'drugs'):
                    simplified = self._simplify_openfda_entry(raw_entry)
                    if simplified:
                        self.openfda_drugs[drug_id] = simplified
                        self._index_openfda_name(simplified.get('drug_name'), drug_id)
                        for name in simplified.get('generic_names', []):
                            self._index_openfda_name(name, drug_id)
                        for name in simplified.get('brand_names', []):
                            self._index_openfda_name(name, drug_id)
        except Exception as exc:
            print(f"Warning: Failed to load OpenFDA data: {exc}")
            self.openfda_drugs = {}
            self.openfda_name_index = {}

    def _simplify_openfda_entry(self, raw_entry: Dict) -> Optional[Dict]:
        if not raw_entry:
            return None
        openfda_data = raw_entry.get('openfda_data', {})
        parsed_dosing = openfda_data.get('parsed_dosing', {}) or {}
        openfda_meta = openfda_data.get('openfda', {}) or {}

        def _clean_list(values):
            if isinstance(values, list):
                return [str(v).strip() for v in values if isinstance(v, str) and v.strip()]
            if isinstance(values, str):
                return [values.strip()] if values.strip() else []
            return []

        # Retain clinical label sections (contraindications, pregnancy, etc.) when
        # the raw OpenFDA dump carries them. These power the co-administration checker.
        label_sections = {}
        for field in _OPENFDA_LABEL_SECTION_FIELDS:
            value = raw_entry.get(field) or openfda_data.get(field)
            text = _openfda_section_text(value)
            if text:
                label_sections[field] = text

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
            },
            'label_sections': label_sections,
        }
        # Keep the entry if it has dosing OR clinical label sections.
        if not any(simplified['parsed_dosing'].values()) and not label_sections:
            return None
        return simplified

    def _index_openfda_name(self, name: Optional[str], drug_id: str) -> None:
        if not name:
            return
        key = name.lower().strip()
        if key:
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

    # ------------------------------------------------------------------
    # Condition labels (openFDA label sections for contraindication checks)
    # ------------------------------------------------------------------

    def _load_condition_labels(self, condition_file: str = 'condition_labels.json') -> None:
        """Load compact openFDA label sections built by scripts/build_condition_labels.py."""
        paths = [
            condition_file,
            os.path.join('data', condition_file),
            os.path.join('..', 'data', condition_file),
            os.path.join('..', 'drug-app', condition_file),
        ]
        actual_path = None
        for path in paths:
            if os.path.exists(path):
                actual_path = path
                break
        if not actual_path:
            return
        try:
            with open(actual_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.condition_labels = data.get('labels', {}) or {}
            for key, entry in self.condition_labels.items():
                self._index_condition_name(key, key)
                self._index_condition_name(entry.get('drug_name'), key)
                for name in entry.get('generic_names', []):
                    self._index_condition_name(name, key)
                for name in entry.get('brand_names', []):
                    self._index_condition_name(name, key)
                for name in entry.get('substance_names', []):
                    self._index_condition_name(name, key)
            print(f"Condition labels loaded: {len(self.condition_labels)} drugs ({actual_path})")
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: Failed to load condition labels: {exc}")
            self.condition_labels = {}
            self.condition_label_index = {}

    def _index_condition_name(self, name: Optional[str], key: str) -> None:
        if not name:
            return
        norm = name.lower().strip()
        if norm:
            self.condition_label_index.setdefault(norm, key)

    def get_label_sections(self, drug_name: str) -> Dict[str, str]:
        """
        Return openFDA label sections for a drug (contraindications, pregnancy,
        drug_interactions, adverse_reactions, etc.). Prefers the dedicated
        condition_labels dataset; falls back to sections retained on OpenFDA data.
        """
        if not drug_name:
            return {}
        query_lower = drug_name.lower().strip()

        # 1) Dedicated condition-labels dataset (exact, then partial).
        key = self.condition_label_index.get(query_lower)
        if not key:
            for name, mapped in self.condition_label_index.items():
                if query_lower in name or name in query_lower:
                    key = mapped
                    break
        if key and key in self.condition_labels:
            sections = self.condition_labels[key].get('sections', {})
            if sections:
                return sections

        # 2) Fallback: sections retained on the OpenFDA lightweight data.
        entry_id = self.openfda_name_index.get(query_lower)
        entry = self.openfda_drugs.get(entry_id) if entry_id else None
        if not entry:
            entry = self._search_openfda_partial(query_lower)
        if entry:
            return entry.get('label_sections', {}) or {}
        return {}

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_category_name(category_entry) -> str:
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

    def _dedupe_forms(self, forms: List[str]) -> List[str]:
        if not forms:
            return []
        normalized = set()
        for form in forms:
            if not form:
                continue
            form = form.strip().title()
            if len(form) > 50:
                continue
            normalized.add(form)
        base_forms = {}
        for form in normalized:
            base = re.split(r'[,;]', form)[0].strip().lower()
            if base not in base_forms:
                base_forms[base] = form
            elif len(form) < len(base_forms[base]):
                base_forms[base] = form
        return sorted(base_forms.values(), key=len)[:4]

    # ------------------------------------------------------------------
    # Public API — search (compact index only, fast)
    # ------------------------------------------------------------------

    def search_drugs(self, query: str) -> List[str]:
        """Search drugs by partial name match. Uses compact index."""
        query_lower = query.lower()
        results = []
        for entry in self.compact_drugs:
            if query_lower in entry['name_lower']:
                results.append(entry['name'])
        return sorted(results)[:50]

    def find_drug(self, drug_name: str) -> Optional[Dict]:
        """
        Return compact drug entry for existence checks and basic field access.
        For full data (interactions, dosing details), use _get_full_drug().
        """
        idx = self.name_to_idx.get(drug_name.lower())
        if idx is not None:
            return self.compact_drugs[idx]
        return None

    def get_all_categories(self) -> List[str]:
        categories = set()
        for entry in self.compact_drugs:
            for cat in entry.get('categories', []):
                if cat:
                    categories.add(cat)
        return sorted(categories)

    def get_drugs_by_category(self, category: str) -> List[str]:
        results = []
        category_lower = category.lower()
        for entry in self.compact_drugs:
            for cat in entry.get('categories', []):
                if category_lower in cat.lower() or cat.lower() in category_lower:
                    results.append(entry['name'])
                    break
        return sorted(set(results))

    def get_alternatives_from_category(self, drug_name: str) -> List[str]:
        entry = self.find_drug(drug_name)
        if not entry or not entry.get('categories'):
            return []
        first_category = entry['categories'][0] if entry['categories'] else ''
        if not first_category:
            return []
        alternatives = self.get_drugs_by_category(first_category)
        return [a for a in alternatives if a.lower() != drug_name.lower()][:10]

    # ------------------------------------------------------------------
    # Public API — full data (streams from disk, cached)
    # ------------------------------------------------------------------

    def get_summary(self, drug_name: str) -> Dict:
        """Get full drug summary. Loads from disk on first access."""
        compact = self.find_drug(drug_name)
        if not compact:
            return {'error': f"Drug '{drug_name}' not found"}

        drug = self._get_full_drug(drug_name)
        if not drug:
            # Fallback: return basic info from compact index
            return {
                'name': compact['name'],
                'drugbank_id': compact['drugbank_ids'].get('primary'),
                'drugbank_ids': compact['drugbank_ids'],
                'type': compact.get('type'),
                'groups': compact.get('groups', []),
                'categories': compact.get('categories', []),
                'description': '',
                'mechanism_of_action': '',
                'dosing': {'has_dosing': compact.get('_has_dosing', False), 'source': None,
                           'frequency': None, 'times_per_day': None, 'routes': [],
                           'strengths': [], 'forms': []},
                'food_interactions': [],
                'interaction_count': len(compact.get('_interaction_ids', set())),
                'interactions_list': [],
                'properties': {},
                'pharmacokinetics': {'half_life': None, 'absorption': None, 'metabolism': None},
                'dosages': [],
            }

        dosing = drug.get('dosing_info', {})
        openfda_dosing_data = self._get_openfda_dosing(drug_name)

        frequency = dosing.get('frequency')
        times_per_day = dosing.get('times_per_day')
        routes = dosing.get('routes')

        if openfda_dosing_data:
            if not frequency:
                frequency = openfda_dosing_data.get('frequency')
            if not times_per_day:
                times_per_day = openfda_dosing_data.get('times_per_day_range') or openfda_dosing_data.get('times_per_day')
            if not routes:
                routes = openfda_dosing_data.get('routes', [])
                if not routes and openfda_dosing_data.get('route'):
                    routes = [openfda_dosing_data['route']] if isinstance(openfda_dosing_data['route'], str) else []

        openfda_full = dosing.get('openfda_full', {})
        if openfda_full:
            if not frequency:
                frequency = openfda_full.get('frequency')
            if not times_per_day:
                times_per_day = openfda_full.get('times_per_day_range') or openfda_full.get('times_per_day')
            if not routes:
                route = openfda_full.get('route')
                if route:
                    routes = [route] if isinstance(route, str) else route

        instructions = dosing.get('instructions', '')
        if not instructions and openfda_dosing_data:
            instructions = openfda_dosing_data.get('instructions', '')
        if not instructions and openfda_full:
            instructions = openfda_full.get('instructions', '')

        if not frequency and instructions:
            instructions_lower = instructions.lower()
            if re.search(r'\b(?:once[\s-]+(?:a\s+)?dai?ly|q\.?d\.?\b|qd\b|\bonce[\s-]+a[\s-]+day)', instructions_lower):
                frequency = 'Once daily'; times_per_day = '1'
            elif re.search(r'\b(?:twice[\s-]+(?:a\s+)?dai?ly|b\.?i\.?d\.?\b|bid\b|twice[\s-]+a[\s-]+day)', instructions_lower):
                frequency = 'Twice daily'; times_per_day = '2'
            elif re.search(r'\b(?:three\s+times[\s-]+(?:a\s+)?dai?ly|t\.?i\.?d\.?\b|tid\b)', instructions_lower):
                frequency = 'Three times daily'; times_per_day = '3'
            elif re.search(r'\b(?:four\s+times[\s-]+(?:a\s+)?dai?ly|q\.?i\.?d\.?\b|qid\b)', instructions_lower):
                frequency = 'Four times daily'; times_per_day = '4'
            elif re.search(r'\b(?:once[\s-]+(?:a\s+)?week(?:ly)?|weekly|every\s+week)', instructions_lower):
                frequency = 'Once weekly'; times_per_day = '0.14'
            else:
                match = re.search(r'\bevery\s+(\d+)\s*(?:hours?|hrs?)\b', instructions_lower)
                if not match:
                    match = re.search(r'\bq(\d+)h\b', instructions_lower)
                if match:
                    hours = int(match.group(1))
                    frequency = f'Every {hours} hours'
                    times_per_day = str(round(24 / hours, 1))

        dosages_list = drug.get('dosages', [])
        if not routes and dosages_list:
            routes_set = set()
            for d in dosages_list:
                if d.get('route'):
                    routes_set.add(normalize_route(d['route']))
            routes = list(routes_set)[:5]

        if routes:
            routes = [normalize_route(r) for r in routes]

        strengths_set = set()
        if dosages_list:
            for d in dosages_list:
                if d.get('strength'):
                    strength = d['strength'].strip()
                    strength = re.sub(r'(\d+)\.0(\s*mg)', r'\1\2', strength)
                    strengths_set.add(strength)
        strengths = sorted(strengths_set)[:5]

        categories = []
        for cat in drug.get('categories', []):
            cat_name = self._normalize_category_name(cat)
            if cat_name:
                categories.append(cat_name)

        summary = {
            'name': drug.get('name'),
            'drugbank_id': drug.get('drugbank_ids', {}).get('primary'),
            'drugbank_ids': drug.get('drugbank_ids', {}),
            'type': drug.get('type'),
            'groups': drug.get('groups', []),
            'description': drug.get('description', ''),
            'mechanism_of_action': drug.get('mechanism_of_action', ''),
            'categories': categories,
            'dosing': {
                'has_dosing': dosing.get('has_dosing', False) or bool(dosages_list),
                'source': dosing.get('source') or ('DrugBank' if dosages_list else None),
                'frequency': frequency,
                'times_per_day': times_per_day,
                'routes': routes if routes else [],
                'strengths': strengths if strengths else [],
                'forms': self._dedupe_forms([d.get('form') for d in dosages_list if d.get('form')]),
            },
            'food_interactions': drug.get('food_interactions', [])[:3],
            'interaction_count': len(drug.get('drug_interactions', [])),
            'interactions_list': drug.get('drug_interactions', []),
            'properties': {},
            'pharmacokinetics': {
                'half_life': drug.get('half_life'),
                'absorption': drug.get('absorption'),
                'metabolism': drug.get('metabolism'),
            },
            'dosages': drug.get('dosages', []),
        }

        for prop in drug.get('experimental_properties', []):
            kind = prop.get('kind')
            if kind in ['Melting Point', 'Water Solubility', 'Molecular Weight', 'logP', 'pKa']:
                summary['properties'][kind] = prop.get('value')

        return summary

    # ------------------------------------------------------------------
    # Compatibility checking
    # ------------------------------------------------------------------

    def check_compatibility(self, drug1_name: str, drug2_name: str) -> Dict:
        result = {
            'drug1': drug1_name,
            'drug2': drug2_name,
            'compatible': True,
            'issues': [],
            'warnings': [],
            'recommendations': [],
            'drug1_data': None,
            'drug2_data': None,
            'interactions': [],
            'routes': {'drug1': [], 'drug2': [], 'common': []},
            'dosing': {'drug1': {}, 'drug2': {}},
        }

        compact1 = self.find_drug(drug1_name)
        compact2 = self.find_drug(drug2_name)

        if not compact1:
            result['issues'].append(f"Drug '{drug1_name}' not found in database")
            result['compatible'] = False
            return result
        if not compact2:
            result['issues'].append(f"Drug '{drug2_name}' not found in database")
            result['compatible'] = False
            return result

        # Load full records for the two drugs being compared (cached after first load)
        drug1 = self._get_full_drug(drug1_name) or compact1
        drug2 = self._get_full_drug(drug2_name) or compact2

        result['drug1_data'] = self.get_summary(drug1_name)
        result['drug2_data'] = self.get_summary(drug2_name)

        if drug1.get('type') == 'biotech':
            result['issues'].append(f"{drug1_name} is a biologic — cannot be 3D printed with standard methods")
            result['compatible'] = False
        if drug2.get('type') == 'biotech':
            result['issues'].append(f"{drug2_name} is a biologic — cannot be 3D printed with standard methods")
            result['compatible'] = False

        dosing1 = drug1.get('dosing_info', {})
        dosing2 = drug2.get('dosing_info', {})

        freq1, times1 = self._extract_dosing(dosing1, drug1_name)
        freq2, times2 = self._extract_dosing(dosing2, drug2_name)

        result['dosing'] = {
            'drug1': {'frequency': freq1, 'times_per_day': times1},
            'drug2': {'frequency': freq2, 'times_per_day': times2},
        }

        if (freq1 or times1) and (freq2 or times2):
            if times1 and times2 and times1 == times2:
                result['recommendations'].append(f"📊 Same dosing frequency: both {freq1 or 'N/A'} ({times1}x/day)")
            elif times1 and times2:
                result['warnings'].append(f"⚠️ Different dosing frequencies: {freq1 or 'N/A'} ({times1}x/day) vs {freq2 or 'N/A'} ({times2}x/day)")
                result['recommendations'].append("📊 Timed-release formulation or separate administration may be needed")

        routes1 = self._collect_routes(drug1, dosing1)
        routes2 = self._collect_routes(drug2, dosing2)
        common = set(r.lower() for r in routes1) & set(r.lower() for r in routes2)
        result['routes'] = {
            'drug1': routes1,
            'drug2': routes2,
            'common': [r for r in routes1 if r.lower() in common],
        }

        drug2_id = compact2['drugbank_ids'].get('primary')
        drug1_id = compact1['drugbank_ids'].get('primary')
        drug1_secondary = set(compact1['drugbank_ids'].get('secondary', []))
        drug2_secondary = set(compact2['drugbank_ids'].get('secondary', []))

        interactions_found = []

        for interaction in drug1.get('drug_interactions', []):
            interaction_id = interaction.get('drugbank_id')
            if interaction_id == drug2_id or interaction_id in drug2_secondary:
                desc = interaction.get('description', '')
                drug_nm = interaction.get('name', drug2_name)
                severity = classify_severity_simple(desc)
                emoji = get_severity_emoji(severity)
                interactions_found.append({'drug': drug_nm, 'description': desc, 'severity': severity})
                if severity == 'severe':
                    result['issues'].append(f"{emoji} SEVERE: {desc}")
                    result['compatible'] = False
                elif severity == 'minor':
                    result['recommendations'].append(f"{emoji} Minor: {desc}")
                else:
                    result['warnings'].append(f"{emoji} Moderate: {desc}")

        for interaction in drug2.get('drug_interactions', []):
            interaction_id = interaction.get('drugbank_id')
            if interaction_id == drug1_id or interaction_id in drug1_secondary:
                desc = interaction.get('description', '')
                drug_nm = interaction.get('name', drug1_name)
                if not any(i['description'] == desc for i in interactions_found):
                    severity = classify_severity_simple(desc)
                    emoji = get_severity_emoji(severity)
                    interactions_found.append({'drug': drug_nm, 'description': desc, 'severity': severity})
                    if severity == 'severe':
                        msg = f"{emoji} SEVERE: {desc}"
                        if msg not in result['issues']:
                            result['issues'].append(msg)
                            result['compatible'] = False
                    elif severity == 'minor':
                        msg = f"{emoji} Minor: {desc}"
                        if msg not in result['recommendations']:
                            result['recommendations'].append(msg)
                    else:
                        msg = f"{emoji} Moderate: {desc}"
                        if msg not in result['warnings']:
                            result['warnings'].append(msg)

        known_class = self._check_drug_class_interactions(drug1, drug2, drug1_name, drug2_name)
        for interaction in known_class:
            if not any(i.get('description', '').lower() == interaction['description'].lower() for i in interactions_found):
                interactions_found.append(interaction)
                result['warnings'].append(f"⚠️ Potential class-based interaction: {interaction['description']}")

        result['interactions'] = interactions_found

        if result['compatible']:
            result['recommendations'].append(f"📊 Drug types: {drug1.get('type', 'unknown')} + {drug2.get('type', 'unknown')}")
            if result['routes']['common']:
                result['recommendations'].append(f"🛣️ Common routes: {', '.join(result['routes']['common'][:5])}")
            elif result['routes']['drug1'] or result['routes']['drug2']:
                r1 = ', '.join(result['routes']['drug1'][:3]) or 'Unknown'
                r2 = ', '.join(result['routes']['drug2'][:3]) or 'Unknown'
                result['recommendations'].append(f"🛣️ Routes: {drug1_name} ({r1}) vs {drug2_name} ({r2})")

        return result

    def find_compatible_alternatives(self, target_drug: str, category: str, limit: int = 10) -> List[Dict]:
        """
        Find drugs from category with NO interactions with target.
        Uses compact index only — no disk reads needed.
        """
        target_compact = self.find_drug(target_drug)
        if not target_compact:
            return []

        target_id = target_compact['drugbank_ids'].get('primary')
        target_secondary = set(target_compact['drugbank_ids'].get('secondary', []))
        target_interaction_ids = target_compact.get('_interaction_ids', set())

        category_drugs = self.get_drugs_by_category(category)
        compatible = []

        for drug_name in category_drugs:
            if drug_name.lower() == target_drug.lower():
                continue
            candidate = self.find_drug(drug_name)
            if not candidate:
                continue

            candidate_id = candidate['drugbank_ids'].get('primary')
            candidate_secondary = set(candidate['drugbank_ids'].get('secondary', []))
            candidate_interaction_ids = candidate.get('_interaction_ids', set())

            has_interaction = (
                (candidate_id and candidate_id in target_interaction_ids)
                or bool(candidate_secondary & target_interaction_ids)
                or (target_id and target_id in candidate_interaction_ids)
                or bool(target_secondary & candidate_interaction_ids)
            )

            if not has_interaction:
                compatible.append({
                    'name': candidate['name'],
                    'type': candidate.get('type'),
                    'has_dosing': candidate.get('_has_dosing', False),
                    'frequency': None,
                    'routes': [],
                })
                if len(compatible) >= limit:
                    break

        return compatible

    def _check_drug_class_interactions(self, drug1: Dict, drug2: Dict, drug1_name: str, drug2_name: str) -> List[Dict]:
        interactions = []

        def get_cats(drug):
            cats = []
            for cat in drug.get('categories', []):
                n = self._normalize_category_name(cat)
                if n:
                    cats.append(n.lower())
            return cats

        categories1 = get_cats(drug1)
        categories2 = get_cats(drug2)
        moa1 = (drug1.get('mechanism_of_action', '') or '').lower()
        moa2 = (drug2.get('mechanism_of_action', '') or '').lower()
        desc1 = (drug1.get('description', '') or '').lower()
        desc2 = (drug2.get('description', '') or '').lower()

        benzo_kw = ['benzodiazepine', 'alprazolam', 'diazepam', 'lorazepam', 'clonazepam',
                    'temazepam', 'oxazepam', 'chlordiazepoxide', 'midazolam']
        beta_kw = ['beta-blocker', 'beta blocker', 'beta-adrenergic', 'nebivolol', 'propranolol',
                   'metoprolol', 'atenolol', 'bisoprolol', 'carvedilol', 'labetalol']

        def matches(kw_list, cats, moa, desc, name):
            return (
                any(kw in ' '.join(cats) or kw in moa or kw in desc for kw in kw_list)
                or any(kw in name.lower() for kw in kw_list if len(kw) > 5)
            )

        is_benzo = matches(benzo_kw, categories1, moa1, desc1, drug1_name) or \
                   matches(benzo_kw, categories2, moa2, desc2, drug2_name)
        is_beta = matches(beta_kw, categories1, moa1, desc1, drug1_name) or \
                  matches(beta_kw, categories2, moa2, desc2, drug2_name)

        if is_benzo and is_beta:
            interactions.append({
                'drug': drug2_name,
                'description': 'Benzodiazepines and beta-blockers may have additive effects on blood pressure lowering and CNS depression.',
                'severity': 'moderate',
                'source': 'known_class_interaction',
            })

        cns_kw = ['cns depressant', 'sedative', 'hypnotic', 'anxiolytic', 'opioid',
                  'barbiturate', 'alcohol', 'antihistamine']
        is_cns1 = any(kw in ' '.join(categories1) or kw in moa1 or kw in desc1 for kw in cns_kw)
        is_cns2 = any(kw in ' '.join(categories2) or kw in moa2 or kw in desc2 for kw in cns_kw)

        if is_cns1 and is_cns2 and not (is_benzo and is_beta):
            interactions.append({
                'drug': drug2_name,
                'description': 'Both medications may cause CNS depression. Combined use may increase risk of drowsiness, dizziness, and impaired coordination.',
                'severity': 'moderate',
                'source': 'known_class_interaction',
            })

        return interactions

    def _extract_dosing(self, dosing: Dict, drug_name: str) -> tuple:
        frequency = dosing.get('frequency')
        times_per_day = dosing.get('times_per_day')

        openfda_dosing_data = self._get_openfda_dosing(drug_name)
        if openfda_dosing_data:
            if not frequency:
                frequency = openfda_dosing_data.get('frequency')
            if not times_per_day:
                times_per_day = openfda_dosing_data.get('times_per_day_range') or openfda_dosing_data.get('times_per_day')

        openfda_full = dosing.get('openfda_full', {})
        if openfda_full:
            if not frequency:
                frequency = openfda_full.get('frequency')
            if not times_per_day:
                times_per_day = openfda_full.get('times_per_day_range') or openfda_full.get('times_per_day')

        instructions = dosing.get('instructions', '')
        if not instructions and openfda_dosing_data:
            instructions = openfda_dosing_data.get('instructions', '')
        if not instructions and openfda_full:
            instructions = openfda_full.get('instructions', '')

        if not frequency and instructions:
            il = instructions.lower()
            if re.search(r'\b(?:once[\s-]+(?:a\s+)?day|once[\s-]+daily|q\.?d\.?\b|qd\b|daily\s+dose)', il):
                frequency = 'Once daily'; times_per_day = '1'
            elif re.search(r'\b(?:twice[\s-]+(?:a\s+)?day|twice[\s-]+daily|b\.?i\.?d\.?\b|bid\b)', il):
                frequency = 'Twice daily'; times_per_day = '2'
            elif re.search(r'\b(?:three\s+times[\s-]+(?:a\s+)?day|t\.?i\.?d\.?\b|tid\b)', il):
                frequency = 'Three times daily'; times_per_day = '3'
            elif re.search(r'\b(?:four\s+times[\s-]+(?:a\s+)?day|q\.?i\.?d\.?\b|qid\b)', il):
                frequency = 'Four times daily'; times_per_day = '4'
            else:
                m = re.search(r'\bevery\s+(\d+)\s+hours?\b', il)
                if m:
                    hours = int(m.group(1))
                    mapping = {24: ('Once daily', '1'), 12: ('Twice daily', '2'),
                               8: ('Three times daily', '3'), 6: ('Four times daily', '4')}
                    if hours in mapping:
                        frequency, times_per_day = mapping[hours]
                    else:
                        frequency = f'Every {hours} hours'
                        times_per_day = str(24 // hours) if hours > 0 else None
                elif re.search(r'\b(?:once\s+weekly|weekly|every\s+week|q\.?w\.?\b)', il):
                    frequency = 'Weekly'; times_per_day = None

        return frequency, times_per_day

    def _collect_routes(self, drug: Dict, dosing: Dict) -> List[str]:
        routes: set = set()

        route_data = dosing.get('routes')
        if route_data:
            if isinstance(route_data, list):
                for r in route_data:
                    routes.add(normalize_route(r))
            elif isinstance(route_data, str):
                routes.add(normalize_route(route_data))

        openfda_full = dosing.get('openfda_full', {})
        if openfda_full:
            for key in ('routes', 'route'):
                val = openfda_full.get(key)
                if val:
                    if isinstance(val, list):
                        for r in val:
                            routes.add(normalize_route(r))
                    elif isinstance(val, str):
                        routes.add(normalize_route(val))

        for d in drug.get('dosages', []):
            if d and d.get('route'):
                routes.add(normalize_route(d['route']))

        return sorted(routes)

    def get_database_info(self) -> Dict:
        return {
            'total_drugs': len(self.compact_drugs),
            'drugs_with_dosing': self.metadata.get('drugs_with_dosing', 0),
            'source': self._db_path or 'No database loaded',
        }


# ------------------------------------------------------------------
# Singleton accessor
# ------------------------------------------------------------------

_drug_service: Optional[DrugService] = None


def get_drug_service() -> DrugService:
    global _drug_service
    if _drug_service is None:
        _drug_service = DrugService()
    return _drug_service
