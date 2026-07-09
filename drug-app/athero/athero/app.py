#!/usr/bin/env python3
"""
Atherosclerosis and Lipoproteins Research Analysis
Streamlit Web Application

Based on the system described in:
"ATHEROSCLEROSIS AND LIPOPROTEINS: MAPPING THOUSANDS OF STUDIES AND BUILDING 
AN INTERACTIVE SYSTEM WITH ARTIFICIAL INTELLIGENCE AGENTS"
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import re

# --- Normalization rules ----------------------------------------------------
# Normalize common lipoprotein variants (e.g., LDL-C, LDLC) to a canonical name
LIPOPROTEIN_NORMALIZATION_PATTERNS = [
    (re.compile(r'\bldl(?:[-\s]?c)?\b'), "LDL"),
    (re.compile(r'\bldlc\b'), "LDL"),
    (re.compile(r'\bldlcholesterol\b'), "LDL"),
    (re.compile(r'low[-\s]?density lipoprotein'), "LDL"),
    (re.compile(r'\bhdl(?:[-\s]?c)?\b'), "HDL"),
    (re.compile(r'\bhdlc\b'), "HDL"),
    (re.compile(r'\bhdlcholesterol\b'), "HDL"),
    (re.compile(r'high[-\s]?density lipoprotein'), "HDL"),
    (re.compile(r'\bvldl(?:[-\s]?c)?\b'), "VLDL"),
    (re.compile(r'very[-\s]?low[-\s]?density lipoprotein'), "VLDL"),
    (re.compile(r'\bidl\b'), "IDL"),
    (re.compile(r'intermediate[-\s]?density lipoprotein'), "IDL"),
    (re.compile(r'\blp\(?a\)?\b'), "Lp(a)"),
    (re.compile(r'\bapoe\b'), "ApoE"),
    (re.compile(r'apolipoprotein[\s-]*e'), "ApoE"),
    (re.compile(r'\bapob\b'), "ApoB"),
    (re.compile(r'apolipoprotein[\s-]*b'), "ApoB"),
    (re.compile(r'\bnon[-\s]?hdl\b'), "Non-HDL"),
    (re.compile(r'\btotal cholesterol\b'), "Total Cholesterol"),
    (re.compile(r'\btriglycerid'), "Triglycerides"),
    (re.compile(r'\btg\b'), "Triglycerides"),
]

BIOMARKER_NORMALIZATION_PATTERNS = [
    (re.compile(r'\bhs[-\s]?crp\b'), "hs-CRP"),
    (re.compile(r'high[-\s]?sensitivity c[-\s]?reactive protein'), "hs-CRP"),
    (re.compile(r'\bcrp\b'), "CRP"),
    (re.compile(r'c[-\s]?reactive protein'), "CRP"),
    (re.compile(r'\btnf[-\s]?alpha\b'), "TNF-α"),
    (re.compile(r'\btnf[-\s]?α\b'), "TNF-α"),
    (re.compile(r'\btnfalpha\b'), "TNF-α"),
    (re.compile(r'\bil[-\s]?6\b'), "IL-6"),
    (re.compile(r'interleukin[-\s]?6'), "IL-6"),
    (re.compile(r'\bil[-\s]?1\b'), "IL-1"),
    (re.compile(r'interleukin[-\s]?1'), "IL-1"),
    (re.compile(r'\bil[-\s]?1β\b'), "IL-1β"),
    (re.compile(r'interleukin[-\s]?1[-\s]?beta'), "IL-1β"),
    (re.compile(r'\bvcam[-\s]?1\b'), "VCAM-1"),
    (re.compile(r'vascular cell adhesion molecule'), "VCAM-1"),
    (re.compile(r'\bicam[-\s]?1\b'), "ICAM-1"),
    (re.compile(r'intercellular adhesion molecule'), "ICAM-1"),
]

# Word cloud
try:
    from wordcloud import WordCloud
    import matplotlib.pyplot as plt
    WORDCLOUD_AVAILABLE = True
except (ImportError, AttributeError):
    WORDCLOUD_AVAILABLE = False

# Vector database for semantic search
try:
    import sys
    sys.path.append(str(Path(__file__).parent.parent / "mirna_analysis"))
    from utils.vector_db import PublicationVectorDB, initialize_vector_db
    VECTOR_DB_AVAILABLE = True
except ImportError:
    VECTOR_DB_AVAILABLE = False

# AI Agents for Q&A, Analysis, and Synthesis
AGENTS_AVAILABLE = False
AGENTS_ERROR = None

try:
    import sys
    import os
    from dotenv import load_dotenv
    
    # Use local agents directory (athero/agents)
    app_dir = Path(__file__).parent
    
    # Check if local agents directory exists
    if not (app_dir / "agents").exists():
        AGENTS_ERROR = f"agents directory not found in: {app_dir}"
    elif not (app_dir / "render_agents.py").exists():
        AGENTS_ERROR = f"render_agents.py not found in: {app_dir}"
    else:
        # Add app directory to path to import local agents
        if str(app_dir) not in sys.path:
            sys.path.insert(0, str(app_dir))
        
        # Import local agents
        from agents.qa_agent import AtheroQAAgent
        from agents.publication_analyzer import PublicationAnalyzer
        from agents.synthesis_agent import ResearchSynthesisAgent
        from agents.literature_review_agent import LiteratureReviewAgent
        from render_agents import render_qa_page, render_publication_analysis_page, render_synthesis_page, render_literature_review_page
        
        # Load environment variables from .env file
        load_dotenv()
        AGENTS_AVAILABLE = True
        AGENTS_ERROR = None
except ImportError as e:
    AGENTS_ERROR = f"Import error: {e}. Make sure dependencies are installed: pip install openai anthropic"
except Exception as e:
    AGENTS_ERROR = f"Error loading AI agents: {e}"
    # Store full traceback for debugging
    import traceback
    if os.getenv("DEBUG", "").lower() == "true":
        AGENTS_ERROR += f"\n{traceback.format_exc()}"

# Page configuration (skip when embedded inside another app)
if os.getenv("ATHERO_EMBEDDED", "0") != "1":
    st.set_page_config(
        page_title="Atherosclerosis & Lipoproteins Research",
        page_icon="❤️",
        layout="wide"
    )

# Styles
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
    st.session_state.all_data = []
    st.session_state.yearly_data = {}


def extract_year_from_date(date_str):
    """Extract year from publication_date field"""
    if not date_str:
        return None
    try:
        # Handle format: "2025-06-01T00:00:00" or "2026-01-30 00:00:00"
        if 'T' in date_str:
            year = int(date_str.split('T')[0].split('-')[0])
        else:
            year = int(date_str.split(' ')[0].split('-')[0])
        return str(year)
    except:
        return None


def _normalize_value_with_patterns(value, patterns):
    """Helper to normalize a single value using provided regex patterns."""
    if value is None:
        return value
    if not isinstance(value, str):
        value = str(value)
    cleaned = value.strip()
    if not cleaned:
        return cleaned
    lowered = cleaned.lower()
    for pattern, replacement in patterns:
        if pattern.search(lowered):
            return replacement
    return cleaned


def normalize_lipoprotein_value(value):
    """Map lipoprotein variants (e.g., LDL-C, LDLC) to a canonical label."""
    return _normalize_value_with_patterns(value, LIPOPROTEIN_NORMALIZATION_PATTERNS)


def normalize_lipoprotein_field(raw_value):
    """Normalize lipoprotein lists/strings while preserving the original type."""
    if isinstance(raw_value, list):
        normalized = [normalize_lipoprotein_value(item) for item in raw_value if item]
        return normalized
    elif isinstance(raw_value, str):
        return normalize_lipoprotein_value(raw_value)
    return raw_value


def normalize_biomarker_value(value):
    """Map biomarker variants (e.g., hs-CRP vs C-reactive protein) to a canonical label."""
    return _normalize_value_with_patterns(value, BIOMARKER_NORMALIZATION_PATTERNS)


def normalize_biomarker_field(raw_value):
    if isinstance(raw_value, list):
        return [normalize_biomarker_value(item) for item in raw_value if item]
    elif isinstance(raw_value, str):
        return normalize_biomarker_value(raw_value)
    return raw_value


def normalize_publication_entities(publications):
    """Apply normalization to publication dictionaries in-place."""
    for pub in publications:
        pub['extracted_lipoproteins'] = normalize_lipoprotein_field(
            pub.get('extracted_lipoproteins', [])
        )
        pub['extracted_biomarkers'] = normalize_biomarker_field(
            pub.get('extracted_biomarkers', [])
        )


def load_athero_data():
    """Load Atherosclerosis data from athero_nlp_only_backup_1763986824_cleaned_genes_no_reviews.json"""
    # Get the app directory and project root
    app_dir = Path(__file__).parent.resolve()
    project_root = app_dir.parent.resolve()
    
    # Try multiple locations for the cleaned genes file (no reviews version)
    possible_paths = [
        app_dir / "athero_nlp_only_backup_1763986824_cleaned_genes_no_reviews.json",
        project_root / "athero_nlp_only_backup_1763986824_cleaned_genes_no_reviews.json",
        Path("athero_nlp_only_backup_1763986824_cleaned_genes_no_reviews.json").resolve(),
        Path(r"C:\Users\Pc\Downloads\myThing\athero\athero_nlp_only_backup_1763986824_cleaned_genes_no_reviews.json"),
    ]
    
    athero_file = None
    for path in possible_paths:
        try:
            if path.exists():
                athero_file = path
                break
        except:
            continue
    
    all_pubs = []
    yearly_counts = {}
    
    if not athero_file or not athero_file.exists():
        st.error(f"Atherosclerosis data file not found: athero_nlp_only_backup_1763986824_cleaned_genes_no_reviews.json")
        st.info("💡 Searched in:")
        for i, p in enumerate(possible_paths, 1):
            exists = "✓" if p.exists() else "✗"
            st.info(f"   {i}. {exists} {p}")
        st.info(f"💡 App directory: {app_dir}")
        st.info(f"💡 Project root: {project_root}")
        st.info("💡 Make sure athero_nlp_only_backup_1763986824_cleaned_genes_no_reviews.json is in the athero directory")
        return [], {}
    
    try:
        with open(athero_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle structure: {"metadata": {...}, "publications": [...]}
        if isinstance(data, dict) and 'publications' in data:
            pubs = data['publications']
        elif isinstance(data, list):
            pubs = data
        else:
            st.error("Unexpected data structure in athero_nlp_only_backup_1763986824_cleaned_genes_no_reviews.json")
            return [], {}
        
        # Process publications
        for pub in pubs:
            # Extract year from publication_date
            pub_date = pub.get('publication_date', '')
            year = extract_year_from_date(pub_date)
            if year:
                pub['year'] = year
                # Filter out 2026 from yearly counts (but keep in dataset)
                if year != '2026':
                    yearly_counts[year] = yearly_counts.get(year, 0) + 1
            else:
                pub['year'] = None
            
            all_pubs.append(pub)
        
        return all_pubs, yearly_counts
    except Exception as e:
        st.error(f"Error loading atherosclerosis data: {e}")
        return [], {}


def load_category_data():
    """Load category data - placeholder for Atherosclerosis"""
    return {}


@st.cache_data
def load_all_data():
    """Load all data with caching"""
    all_pubs, yearly_counts = load_athero_data()
    normalize_publication_entities(all_pubs)
    categories = load_category_data()
    return all_pubs, yearly_counts, categories


def render_sidebar():
    """Render sidebar with filters and navigation"""
    with st.sidebar:
        st.title("❤️ Atherosclerosis")
        st.title("& Lipoproteins")
        
        st.markdown("---")
        
        # Navigation
        menu_options = [
            "📊 Overview",
            "📉 Filter & Visualize",
            "📅 Trend by Entity",
            "☁️ Word Clouds",
            "📋 Data Table",
            "🤖 AI Q&A",
            "📝 Publication Analysis",
            "🔬 Research Synthesis",
            "📚 Literature Review",
            "📖 Publications",
            "⚙️ Settings",
        ]
        page = st.radio("Navigate", menu_options, label_visibility="collapsed")
        
        return page, None, None, None


def render_overview_page(all_data, yearly_counts, categories):
    """Render overview page with key metrics"""
    st.markdown('<div class="main-header">❤️ Atherosclerosis & Lipoproteins Research Overview</div>', 
                unsafe_allow_html=True)
    
    st.markdown("""
    **AI-Powered Knowledge Extraction System**  
    *Mapping thousands of studies and building an interactive system with artificial intelligence agents*
    """)
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📚 Total Publications",
            value=f"{len(all_data):,}",
            delta=f"+{yearly_counts.get('2025', 0):,} in 2025" if yearly_counts else "0 in 2025"
        )
    
    with col2:
        if yearly_counts:
            years = sorted([int(y) for y in yearly_counts.keys() if y])
            year_range = f"{min(years)}-{max(years)}" if years else "N/A"
            st.metric(
                label="📅 Years Covered",
                value=year_range,
                delta=f"{len(years)} years" if years else "0 years"
            )
        else:
            st.metric(label="📅 Years Covered", value="2020-2025", delta="6 years")
    
    with col3:
        peak_year = max(yearly_counts.items(), key=lambda x: x[1]) if yearly_counts else ("N/A", 0)
        st.metric(
            label="📈 Peak Year",
            value=peak_year[0],
            delta=f"{peak_year[1]:,} papers"
        )
    
    with col4:
        avg_per_year = len(all_data) / len(yearly_counts) if yearly_counts else 0
        st.metric(
            label="📊 Avg per Year",
            value=f"{avg_per_year:,.0f}",
            delta=f"{len(yearly_counts)} years" if yearly_counts else "0 years"
        )
    
    st.markdown("---")
    
    # Quick visualization
    col1, col2 = st.columns(2)
    
    with col1:
        # Cumulative Publications
        st.subheader("📈 Cumulative Publications")
        if yearly_counts:
            df_cum = pd.DataFrame(list(yearly_counts.items()), columns=['Year', 'Publications'])
            df_cum['Year'] = df_cum['Year'].astype(int)
            df_cum = df_cum.sort_values('Year')
            df_cum['Cumulative'] = df_cum['Publications'].cumsum()
            
            fig = px.area(df_cum, x='Year', y='Cumulative',
                         title='Cumulative Publications Over Time',
                         color_discrete_sequence=['#d32f2f'])
            fig.update_traces(line=dict(width=2))
            st.plotly_chart(fig, width='stretch')
        
        # Publication trend
        st.subheader("📈 Publications by Year")
        if yearly_counts:
            df = pd.DataFrame(list(yearly_counts.items()), columns=['Year', 'Count'])
            df['Year'] = df['Year'].astype(int)
            df = df.sort_values('Year')
            
            fig = px.line(df, x='Year', y='Count', 
                         title='Annual Publication Count',
                         markers=True)
            fig.update_traces(line=dict(width=3, color='#d32f2f'))
            st.plotly_chart(fig, width='stretch')
    
    with col2:
        # Top Lipoproteins
        st.subheader("🧬 Top Lipoproteins Mentioned")
        
        lipoprotein_counter = Counter()
        for pub in all_data:
            lipoproteins = pub.get('extracted_lipoproteins', [])
            if isinstance(lipoproteins, list):
                lipoprotein_counter.update(lipoproteins)
            elif lipoproteins:
                lipoprotein_counter[lipoproteins] += 1
        
        if lipoprotein_counter:
            top_lipoproteins = lipoprotein_counter.most_common(10)
            df = pd.DataFrame(top_lipoproteins, columns=['name', 'count'])
            
            fig = px.pie(df, values='count', names='name',
                        title='Top 10 Lipoproteins',
                        hole=0.0,
                        color_discrete_sequence=px.colors.qualitative.Set3)
            
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(showlegend=True, height=450)
            st.plotly_chart(fig, width='stretch')
            
            st.caption(f"Based on {sum(lipoprotein_counter.values()):,} lipoprotein mentions")
        else:
            st.info("No lipoprotein data available. Run extraction to populate data.")
        
        # Top Biomarkers
        st.subheader("🔬 Top Biomarkers Mentioned")
        
        biomarker_counter = Counter()
        for pub in all_data:
            biomarkers = pub.get('extracted_biomarkers', [])
            if isinstance(biomarkers, list):
                biomarker_counter.update(biomarkers)
            elif biomarkers:
                biomarker_counter[biomarkers] += 1
        
        if biomarker_counter:
            top_biomarkers = biomarker_counter.most_common(10)
            df_biomarkers = pd.DataFrame(top_biomarkers, columns=['Biomarker', 'Count'])
            
            fig = px.bar(df_biomarkers, x='Count', y='Biomarker',
                        orientation='h',
                        title='Top 10 Biomarkers',
                        color='Count',
                        color_continuous_scale='Reds')
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No biomarker data available")
    
    # Structured Data Table
    st.markdown("---")
    st.subheader("📋 Structured Data Table")
    st.markdown("View detailed structured data from atherosclerosis and lipoprotein publications")
    
    if all_data:
        st.success(f"✅ Loaded {len(all_data):,} publications")
        
        # Filters for the table
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Filter by thematic category
            all_categories = sorted(set(
                item for sublist in [pub.get('extracted_thematic_categories', []) for pub in all_data if pub.get('extracted_thematic_categories')]
                for item in (sublist if isinstance(sublist, list) else [sublist])
            ))
            selected_category = st.selectbox(
                "Filter by Thematic Category:",
                ["All"] + all_categories,
                key="table_category_filter"
            )
        
        with col2:
            # Filter by study type
            study_types = sorted(set(
                str(item.get('study_type', 'Unknown')).strip().lower() 
                for item in all_data 
                if item.get('study_type') and str(item.get('study_type')).strip()
            ))
            study_types_display = [s.replace('_', ' ').title() for s in study_types]
            study_type_map = {display: orig for display, orig in zip(study_types_display, study_types)}
            
            selected_study_type = st.selectbox(
                "Filter by Study Type:",
                ["All"] + study_types_display,
                key="table_study_filter"
            )
        
        with col3:
            # Filter by year
            all_years = sorted(set(
                int(item.get('year', 0))
                for item in all_data 
                if item.get('year')
            ), reverse=True)
            selected_year = st.selectbox(
                "Filter by Year:",
                ["All"] + [str(y) for y in all_years],
                key="table_year_filter"
            )
        
        # Apply filters
        filtered_table_data = all_data
        if selected_category != "All":
            filtered_table_data = [
                item for item in filtered_table_data 
                if selected_category in (item.get('extracted_thematic_categories', []) if isinstance(item.get('extracted_thematic_categories'), list) else [item.get('extracted_thematic_categories')])
            ]
        if selected_study_type != "All":
            study_type_value = study_type_map.get(selected_study_type, selected_study_type.lower())
            filtered_table_data = [
                item for item in filtered_table_data 
                if str(item.get('study_type', '')).strip().lower() == study_type_value
            ]
        if selected_year != "All":
            filtered_table_data = [
                item for item in filtered_table_data 
                if str(item.get('year', '')) == selected_year
            ]
        
        st.info(f"Showing {len(filtered_table_data):,} of {len(all_data):,} publications")
        
        # Prepare table data
        table_rows = []
        for item in filtered_table_data:
            # Format list fields
            lipoproteins = item.get('extracted_lipoproteins', [])
            lp_str = ', '.join(lipoproteins[:3]) if isinstance(lipoproteins, list) else str(lipoproteins) if lipoproteins else ''
            if isinstance(lipoproteins, list) and len(lipoproteins) > 3:
                lp_str += f" (+{len(lipoproteins)-3} more)"
            
            biomarkers = item.get('extracted_biomarkers', [])
            bio_str = ', '.join(biomarkers[:2]) if isinstance(biomarkers, list) else str(biomarkers) if biomarkers else ''
            if isinstance(biomarkers, list) and len(biomarkers) > 2:
                bio_str += f" (+{len(biomarkers)-2} more)"
            
            interventions = item.get('extracted_therapeutic_interventions', [])
            int_str = ', '.join(interventions[:2]) if isinstance(interventions, list) else str(interventions) if interventions else ''
            if isinstance(interventions, list) and len(interventions) > 2:
                int_str += f" (+{len(interventions)-2} more)"
            
            table_rows.append({
                'Title': (item.get('title') or '')[:100] + ('...' if len(item.get('title') or '') > 100 else ''),
                'Year': item.get('year', ''),
                'Study Type': item.get('study_type', '').replace('_', ' ').title() if item.get('study_type') else '',
                'Lipoproteins': lp_str[:50] + ('...' if len(lp_str) > 50 else ''),
                'Biomarkers': bio_str[:50] + ('...' if len(bio_str) > 50 else ''),
                'Interventions': int_str[:50] + ('...' if len(int_str) > 50 else ''),
                'Patient Count': item.get('patient_count', ''),
                'PMID': item.get('pmid', '')
            })
        
        # Create DataFrame
        df_table = pd.DataFrame(table_rows)
        
        # Display table with pagination (using st.write to avoid pyarrow dependency)
        try:
            st.dataframe(
                df_table,
                width='stretch',
                height=400,
                hide_index=True
            )
        except Exception:
            # Fallback if pyarrow is not available
            st.write(df_table.to_html(escape=False, index=False), unsafe_allow_html=True)
        
        # Export options
        csv = df_table.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"athero_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("⚠️ No publication data available. Run `python extract_athero.py` to extract data from PubMed.")


def render_search_page(all_data):
    """Render search and filter page"""
    st.header("🔍 Search Publications")
    
    # Search box
    search_query = st.text_input(
        "Search by title, abstract, or keywords",
        placeholder="Enter search terms..."
    )
    
    # Filter results
    if search_query:
        results = []
        query_lower = search_query.lower()
        
        for pub in all_data:
            title = (pub.get('title') or '').lower()
            abstract = (pub.get('abstract') or '').lower()
            
            if query_lower in title or query_lower in abstract:
                results.append(pub)
        
        st.info(f"Found {len(results)} publications matching '{search_query}'")
        
        # Display results
        for i, pub in enumerate(results[:50], 1):  # Limit to 50 results
            with st.expander(f"📄 {i}. {pub.get('title') or 'No title'}"):
                st.markdown(f"**PMID:** {pub.get('pmid') or 'N/A'}")
                st.markdown(f"**Year:** {pub.get('year') or 'N/A'}")
                abstract = pub.get('abstract')
                if abstract:
                    st.markdown(f"**Abstract:** {abstract[:500]}...")
                
                # Action buttons
                col1, col2 = st.columns(2)
                with col1:
                    if pub.get('pmid'):
                        st.link_button(
                            "View on PubMed",
                            f"https://pubmed.ncbi.nlm.nih.gov/{pub['pmid']}/"
                        )
    else:
        st.info("Enter search terms to find publications")


def render_advanced_filters_page(all_data):
    """Render advanced filters page"""
    st.header("🎯 Advanced Filters")
    
    # Extract unique values for filters
    all_lipoproteins = set()
    all_biomarkers = set()
    all_interventions = set()
    all_risk_factors = set()
    
    for pub in all_data:
        for field, target_set in [
            ('extracted_lipoproteins', all_lipoproteins),
            ('extracted_biomarkers', all_biomarkers),
            ('extracted_therapeutic_interventions', all_interventions),
            ('extracted_risk_factors', all_risk_factors)
        ]:
            values = pub.get(field, [])
            if isinstance(values, list):
                target_set.update(values)
            elif values:
                target_set.add(values)
    
    # Create filter section
    st.markdown("### 🔍 Filters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_lipoprotein = st.selectbox(
            "Lipoprotein",
            options=["All"] + sorted(list(all_lipoproteins))[:50],
            index=0
        )
        
        selected_biomarker = st.selectbox(
            "Biomarker",
            options=["All"] + sorted(list(all_biomarkers))[:50],
            index=0
        )
    
    with col2:
        selected_intervention = st.selectbox(
            "Therapeutic Intervention",
            options=["All"] + sorted(list(all_interventions))[:50],
            index=0
        )
        
        selected_risk_factor = st.selectbox(
            "Risk Factor",
            options=["All"] + sorted(list(all_risk_factors))[:50],
            index=0
        )
    
    # Year range
    col1, col2 = st.columns(2)
    with col1:
        start_year = st.number_input(
            "Start Year",
            min_value=2015,
            max_value=2025,
            value=2015,
            step=1
        )
    
    with col2:
        end_year = st.number_input(
            "End Year",
            min_value=2015,
            max_value=2025,
            value=2025,
            step=1
        )
    
    # Action buttons
    col1, col2, col3 = st.columns([1, 1, 3])
    
    with col1:
        apply_filters = st.button("🔍 Apply Filters", type="primary")
    
    with col2:
        load_all = st.button("📄 Load All Papers")
    
    # Apply filters
    if apply_filters or load_all:
        filtered_results = []
        
        if load_all:
            filtered_results = all_data
        else:
            for pub in all_data:
                year = pub.get('year')
                
                # Year filter (exclude 2026)
                try:
                    pub_year = int(year) if year else 0
                    if pub_year == 2026:  # Explicitly exclude 2026
                        continue
                    if pub_year < start_year or pub_year > end_year:
                        continue
                except:
                    continue
                
                # Lipoprotein filter
                if selected_lipoprotein != "All":
                    lipoproteins = pub.get('extracted_lipoproteins', [])
                    if isinstance(lipoproteins, list):
                        if selected_lipoprotein not in lipoproteins:
                            continue
                    elif lipoproteins != selected_lipoprotein:
                        continue
                
                # Biomarker filter
                if selected_biomarker != "All":
                    biomarkers = pub.get('extracted_biomarkers', [])
                    if isinstance(biomarkers, list):
                        if selected_biomarker not in biomarkers:
                            continue
                    elif biomarkers != selected_biomarker:
                        continue
                
                # Intervention filter
                if selected_intervention != "All":
                    interventions = pub.get('extracted_therapeutic_interventions', [])
                    if isinstance(interventions, list):
                        if selected_intervention not in interventions:
                            continue
                    elif interventions != selected_intervention:
                        continue
                
                # Risk factor filter
                if selected_risk_factor != "All":
                    risk_factors = pub.get('extracted_risk_factors', [])
                    if isinstance(risk_factors, list):
                        if selected_risk_factor not in risk_factors:
                            continue
                    elif risk_factors != selected_risk_factor:
                        continue
                
                filtered_results.append(pub)
        
        # Display results
        if filtered_results:
            st.success(f"✅ Found {len(filtered_results)} papers")
            
            # Display results in expandable cards
            st.markdown("---")
            for i, pub in enumerate(filtered_results[:100], 1):  # Limit to 100 results
                with st.expander(f"📄 {i}. {pub.get('title') or 'No title'}"):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"**PMID:** {pub.get('pmid') or 'N/A'}")
                        st.markdown(f"**Year:** {pub.get('year') or 'N/A'}")
                        st.markdown(f"**Journal:** {pub.get('journal') or 'N/A'}")
                        
                        abstract = pub.get('abstract')
                        if abstract:
                            st.markdown("**Abstract:**")
                            st.text(abstract[:500] + "..." if len(abstract) > 500 else abstract)
                    
                    with col2:
                        if pub.get('pmid'):
                            st.link_button(
                                "View on PubMed",
                                f"https://pubmed.ncbi.nlm.nih.gov/{pub['pmid']}/",
                            )
            
            if len(filtered_results) > 100:
                st.info(f"Showing first 100 of {len(filtered_results)} results")
        else:
            st.warning("No papers found matching your filters. Try adjusting your criteria.")
    else:
        st.info("👆 Set your filters above and click 'Apply Filters' to search")


def render_filter_visualize_page(all_data):
    """Render filters and visualization page with dynamic charts"""
    st.header("📉 Filter & Visualize")
    
    st.markdown("Apply filters below and see visualizations update in real-time!")
    
    # Extract unique values
    lipoprotein_values = set()
    for pub in all_data:
        values = pub.get('extracted_lipoproteins')
        if not values:
            continue
        items = values if isinstance(values, list) else [values]
        for item in items:
            normalized = normalize_lipoprotein_value(item)
            if normalized:
                lipoprotein_values.add(normalized)
    
    if not lipoprotein_values:
        # Fallback to raw values if normalization removed everything
        for pub in all_data:
            values = pub.get('extracted_lipoproteins')
            if not values:
                continue
            items = values if isinstance(values, list) else [values]
            for item in items:
                if item:
                    lipoprotein_values.add(str(item))
    
    all_lipoproteins = sorted(list(lipoprotein_values))
    
    all_biomarkers = sorted(list(set(
        item for sublist in [pub.get('extracted_biomarkers', []) for pub in all_data if pub.get('extracted_biomarkers')]
        for item in (sublist if isinstance(sublist, list) else [sublist])
    )))
    
    # Filters Section
    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            selected_lipoprotein = st.selectbox(
                "Lipoprotein",
                options=["All"] + all_lipoproteins,
                index=0,
                key="viz_lipoprotein"
            )
        
        with col2:
            selected_biomarker = st.text_input(
                "Biomarker (comma-separated)",
                placeholder="e.g., CRP, hs-CRP, TMAO",
                key="viz_biomarker"
            )
        
        with col3:
            selected_intervention = st.text_input(
                "Therapeutic Intervention (comma-separated)",
                placeholder="e.g., statin, aspirin",
                key="viz_intervention"
            )
        
        # Date range selector
        # Get available years from data (excluding 2026) and convert to int
        years = sorted(set(
            int(p.get('year')) for p in all_data 
            if p.get('year') and str(p.get('year')).isdigit() and int(p.get('year')) != 2026
        ))
        min_year = int(min(years)) if years else 2015
        max_year = int(max(years)) if years else 2025
        if max_year == 2026:
            max_year = 2025
        
        year_range = st.slider(
            "Year Range",
            min_value=min_year,
            max_value=max_year,
            value=(min_year, max_year),
            step=1,
            key="viz_year_range"
        )
        start_year, end_year = year_range
    
    # Apply filters
    filtered_results = []
    
    for pub in all_data:
        title = (pub.get('title') or '').lower()
        abstract = (pub.get('abstract') or '').lower()
        text = f"{title} {abstract}"
        year = pub.get('year')
        
        # Year filter (exclude 2026)
        try:
            pub_year = int(year) if year else 0
            if pub_year == 2026:  # Explicitly exclude 2026
                continue
            if pub_year < start_year or pub_year > end_year:
                continue
        except:
            continue
        
        # Lipoprotein filter
        if selected_lipoprotein != "All":
            lipoproteins = pub.get('extracted_lipoproteins', [])
            if isinstance(lipoproteins, list):
                if selected_lipoprotein not in lipoproteins:
                    continue
            elif lipoproteins != selected_lipoprotein:
                continue
        
        # Biomarker filter
        if selected_biomarker.strip():
            biomarker_terms = [term.strip().lower() for term in selected_biomarker.split(',')]
            biomarkers = pub.get('extracted_biomarkers', [])
            if isinstance(biomarkers, list):
                if not any(any(term in str(b).lower() for b in biomarkers) for term in biomarker_terms):
                    if not any(term in text for term in biomarker_terms):
                        continue
            elif not any(term in text for term in biomarker_terms):
                continue
        
        # Intervention filter
        if selected_intervention.strip():
            intervention_terms = [term.strip().lower() for term in selected_intervention.split(',')]
            interventions = pub.get('extracted_therapeutic_interventions', [])
            if isinstance(interventions, list):
                if not any(any(term in str(i).lower() for i in interventions) for term in intervention_terms):
                    if not any(term in text for term in intervention_terms):
                        continue
            elif not any(term in text for term in intervention_terms):
                continue
        
        filtered_results.append(pub)
    
    # Display metrics
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📚 Filtered Papers", f"{len(filtered_results):,}")
    
    with col2:
        unique_years = len(set(p.get('year') for p in filtered_results if p.get('year') and p.get('year') != 2026))
        st.metric("📅 Years Covered", unique_years)
    
    with col3:
        avg_per_year = len(filtered_results) / unique_years if unique_years > 0 else 0
        st.metric("📊 Avg per Year", f"{avg_per_year:.0f}")
    
    with col4:
        pct_of_total = (len(filtered_results) / len(all_data) * 100) if len(all_data) > 0 else 0
        st.metric("📈 % of Total", f"{pct_of_total:.1f}%")
    
    if len(filtered_results) == 0:
        st.warning("⚠️ No papers match your filters. Try adjusting your criteria.")
        return
    
    # Visualizations
    st.markdown("---")
    
    # Show active filters
    active_filters = []
    if selected_lipoprotein != "All":
        active_filters.append(f"Lipoprotein: {selected_lipoprotein}")
    if selected_biomarker.strip():
        active_filters.append(f"Biomarker: {selected_biomarker}")
    if selected_intervention.strip():
        active_filters.append(f"Intervention: {selected_intervention}")
    if start_year != 2015 or end_year != 2025:
        active_filters.append(f"Years: {start_year}-{end_year}")
    
    if active_filters:
        st.info(f"🔍 Active Filters: {', '.join(active_filters)}")
    
    # 1. Publication Timeline
    st.subheader("📈 Publication Timeline")
    # Exclude 2026 from year counts
    year_counts = Counter(pub.get('year') for pub in filtered_results if pub.get('year') and pub.get('year') != 2026)
    if year_counts:
        df_timeline = pd.DataFrame(list(year_counts.items()), columns=['Year', 'Count'])
        df_timeline['Year'] = df_timeline['Year'].astype(int)
        df_timeline = df_timeline.sort_values('Year')
        
        # Filter to selected year range for display and exclude 2026
        df_timeline = df_timeline[(df_timeline['Year'] >= start_year) & (df_timeline['Year'] <= end_year) & (df_timeline['Year'] != 2026)]
        
        title_suffix = f" ({selected_lipoprotein})" if selected_lipoprotein != "All" else ""
        fig = px.line(df_timeline, x='Year', y='Count',
                     title=f'Publications Over Time{title_suffix}',
                     markers=True)
        fig.update_traces(line=dict(width=3, color='#d32f2f'))
        fig.update_layout(hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)
    
    # Two column layout for more visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        # 2. Top Lipoproteins Distribution
        st.subheader("🧬 Top Lipoproteins")
        
        lipoprotein_counter = Counter()
        for pub in filtered_results[:1000]:  # Sample for performance
            lipoproteins = pub.get('extracted_lipoproteins', [])
            if isinstance(lipoproteins, list):
                lipoprotein_counter.update(lipoproteins)
            elif lipoproteins:
                lipoprotein_counter[lipoproteins] += 1
        
        if lipoprotein_counter:
            top_10 = lipoprotein_counter.most_common(10)
            df_lp = pd.DataFrame(top_10, columns=['Lipoprotein', 'Count'])
            
            fig = px.bar(df_lp, y='Lipoprotein', x='Count',
                       title='Top 10 Lipoproteins in Filtered Results',
                       orientation='h',
                       color='Count',
                       color_continuous_scale='Reds')
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No lipoproteins found in filtered results.")
    
    with col2:
        # 3. Top Biomarkers
        st.subheader("🔬 Top Biomarkers")
        
        biomarker_counter = Counter()
        for pub in filtered_results[:1000]:
            biomarkers = pub.get('extracted_biomarkers', [])
            if isinstance(biomarkers, list):
                biomarker_counter.update(biomarkers)
            elif biomarkers:
                biomarker_counter[biomarkers] += 1
        
        if biomarker_counter:
            top_10 = biomarker_counter.most_common(10)
            df_bio = pd.DataFrame(top_10, columns=['Biomarker', 'Count'])
            
            fig = px.bar(df_bio, y='Biomarker', x='Count',
                       title='Top 10 Biomarkers in Filtered Results',
                       orientation='h',
                       color='Count',
                       color_continuous_scale='Blues')
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No biomarkers found in filtered results.")
    
    # 4. Cumulative Publications
    st.subheader("📈 Cumulative Publications")
    if year_counts:
        df_cum = pd.DataFrame(list(year_counts.items()), columns=['Year', 'Publications'])
        df_cum['Year'] = df_cum['Year'].astype(int)
        df_cum = df_cum.sort_values('Year')
        df_cum['Cumulative'] = df_cum['Publications'].cumsum()
        
        fig = px.area(df_cum, x='Year', y='Cumulative',
                     title='Cumulative Publications Over Time',
                     color_discrete_sequence=['#d32f2f'])
        fig.update_traces(line=dict(width=2))
        st.plotly_chart(fig, use_container_width=True)
    
    # 5. Top Therapeutic Interventions and Risk Factors
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💊 Top Therapeutic Interventions")
        intervention_counter = Counter()
        
        for pub in filtered_results[:500]:  # Sample for performance
            interventions = pub.get('extracted_therapeutic_interventions', [])
            if isinstance(interventions, list):
                intervention_counter.update(interventions)
            elif interventions:
                intervention_counter[interventions] += 1
        
        if intervention_counter:
            top_interventions = intervention_counter.most_common(15)
            df_int = pd.DataFrame(top_interventions, columns=['Intervention', 'Mentions'])
            
            fig = px.bar(df_int, x='Mentions', y='Intervention',
                        orientation='h',
                        title='Top 15 Therapeutic Interventions',
                        color='Mentions',
                        color_continuous_scale='Greens')
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No interventions detected in filtered papers")
    
    with col2:
        st.subheader("⚠️ Top Risk Factors")
        risk_factor_counter = Counter()
        
        for pub in filtered_results[:500]:
            risk_factors = pub.get('extracted_risk_factors', [])
            if isinstance(risk_factors, list):
                risk_factor_counter.update(risk_factors)
            elif risk_factors:
                risk_factor_counter[risk_factors] += 1
        
        if risk_factor_counter:
            top_risks = risk_factor_counter.most_common(15)
            df_risks = pd.DataFrame(top_risks, columns=['Risk Factor', 'Mentions'])
            
            fig = px.bar(df_risks, x='Mentions', y='Risk Factor',
                        orientation='h',
                        title='Top 15 Risk Factors',
                        color='Mentions',
                        color_continuous_scale='Oranges')
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No risk factors detected in filtered papers")
    
    # Export option
    st.markdown("---")
    if st.button("📥 Export Filtered Data", key="export_viz"):
        filename = f"athero_filtered_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(filtered_results, f, indent=2, ensure_ascii=False)
        st.success(f"✅ Exported {len(filtered_results)} papers to {filename}")


def render_trend_by_entity_page(all_data):
    """Render entity-specific trend analysis page"""
    st.header("📅 Trend Analysis by Entity")
    
    st.markdown("Select entities to see their publication trends over time.")
    
    # Extract unique entities from data with counts (only show ones that exist)
    lipoprotein_counter = Counter()
    biomarker_counter = Counter()
    intervention_counter = Counter()
    drug_counter = Counter()
    gene_counter = Counter()
    protein_counter = Counter()
    risk_factor_counter = Counter()
    comorbidity_counter = Counter()
    
    for pub in all_data:
        # Lipoproteins
        lipoproteins = pub.get('extracted_lipoproteins', [])
        if isinstance(lipoproteins, list):
            lipoprotein_counter.update(lipoproteins)
        elif lipoproteins:
            lipoprotein_counter[lipoproteins] += 1
        
        # Biomarkers
        biomarkers = pub.get('extracted_biomarkers', [])
        if isinstance(biomarkers, list):
            biomarker_counter.update(biomarkers)
        elif biomarkers:
            biomarker_counter[biomarkers] += 1
        
        # Interventions
        interventions = pub.get('extracted_therapeutic_interventions', [])
        if isinstance(interventions, list):
            intervention_counter.update(interventions)
        elif interventions:
            intervention_counter[interventions] += 1
        
        # Drugs
        drugs = pub.get('extracted_drugs', [])
        if isinstance(drugs, list):
            for drug in drugs:
                if isinstance(drug, dict):
                    drug_counter[drug.get('name', drug)] += 1
                else:
                    drug_counter[drug] += 1
        elif drugs:
            drug_counter[drugs] += 1
        
        # Genes
        genes = pub.get('extracted_genes', [])
        if isinstance(genes, list):
            gene_counter.update(genes)
        elif genes:
            gene_counter[genes] += 1
        
        # Proteins
        proteins = pub.get('extracted_proteins', [])
        if isinstance(proteins, list):
            protein_counter.update(proteins)
        elif proteins:
            protein_counter[proteins] += 1
        
        # Risk factors
        risk_factors = pub.get('extracted_risk_factors', [])
        if isinstance(risk_factors, list):
            risk_factor_counter.update(risk_factors)
        elif risk_factors:
            risk_factor_counter[risk_factors] += 1
        
        # Comorbidities
        comorbidities = pub.get('extracted_comorbidities', [])
        if isinstance(comorbidities, list):
            comorbidity_counter.update(comorbidities)
        elif comorbidities:
            comorbidity_counter[comorbidities] += 1
    
    # Selection interface
    st.markdown("### 🎯 Select Entities to Analyze")
    
    # Create tabs for different entity types
    tab1, tab2, tab3, tab4 = st.tabs(["🧬 Lipoproteins & Biomarkers", "💊 Drugs & Interventions", "🧪 Genes & Proteins", "⚠️ Risk Factors & Comorbidities"])
    
    selected_lipoproteins = []
    selected_biomarkers = []
    selected_interventions = []
    selected_drugs = []
    selected_genes = []
    selected_proteins = []
    selected_risk_factors = []
    selected_comorbidities = []
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🧬 Lipoproteins**")
            # Only show lipoproteins that exist (sorted by frequency)
            if lipoprotein_counter:
                common_lipoproteins = [lp for lp, count in lipoprotein_counter.most_common(50)]
                selected_lipoproteins = st.multiselect(
                    "Choose lipoproteins (showing only those in data)",
                    options=common_lipoproteins,
                    default=[],
                    key="trend_lipoproteins",
                    help=f"Found {len(lipoprotein_counter)} unique lipoproteins in data"
                )
            else:
                st.info("No lipoproteins found in data")
            
            custom_lp = st.text_input(
                "Add custom lipoprotein",
                placeholder="e.g., Lp(a)",
                key="custom_lipoprotein"
            )
            if custom_lp.strip():
                if custom_lp not in selected_lipoproteins:
                    selected_lipoproteins.append(custom_lp)
        
        with col2:
            st.markdown("**🔬 Biomarkers**")
            if biomarker_counter:
                common_biomarkers = [bio for bio, count in biomarker_counter.most_common(50)]
                selected_biomarkers = st.multiselect(
                    "Choose biomarkers (showing only those in data)",
                    options=common_biomarkers,
                    default=[],
                    key="trend_biomarkers",
                    help=f"Found {len(biomarker_counter)} unique biomarkers in data"
                )
            else:
                st.info("No biomarkers found in data")
            
            custom_bio = st.text_input(
                "Add custom biomarker",
                placeholder="e.g., hs-CRP",
                key="custom_biomarker"
            )
            if custom_bio.strip():
                if custom_bio not in selected_biomarkers:
                    selected_biomarkers.append(custom_bio)
    
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**💊 Drugs**")
            if drug_counter:
                common_drugs = [drug for drug, count in drug_counter.most_common(50)]
                selected_drugs = st.multiselect(
                    "Choose drugs (showing only those in data)",
                    options=common_drugs,
                    default=[],
                    key="trend_drugs",
                    help=f"Found {len(drug_counter)} unique drugs in data"
                )
            else:
                st.info("No drugs found in data")
        
        with col2:
            st.markdown("**💉 Therapeutic Interventions**")
            if intervention_counter:
                common_interventions = [intv for intv, count in intervention_counter.most_common(50)]
                selected_interventions = st.multiselect(
                    "Choose interventions (showing only those in data)",
                    options=common_interventions,
                    default=[],
                    key="trend_interventions",
                    help=f"Found {len(intervention_counter)} unique interventions in data"
                )
            else:
                st.info("No interventions found in data")
    
    with tab3:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🧪 Genes**")
            if gene_counter:
                common_genes = [gene for gene, count in gene_counter.most_common(50)]
                selected_genes = st.multiselect(
                    "Choose genes (showing only those in data)",
                    options=common_genes,
                    default=[],
                    key="trend_genes",
                    help=f"Found {len(gene_counter)} unique genes in data"
                )
            else:
                st.info("No genes found in data")
        
        with col2:
            st.markdown("**⚛️ Proteins**")
            if protein_counter:
                common_proteins = [prot for prot, count in protein_counter.most_common(50)]
                selected_proteins = st.multiselect(
                    "Choose proteins (showing only those in data)",
                    options=common_proteins,
                    default=[],
                    key="trend_proteins",
                    help=f"Found {len(protein_counter)} unique proteins in data"
                )
            else:
                st.info("No proteins found in data")
    
    with tab4:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**⚠️ Risk Factors**")
            if risk_factor_counter:
                common_risks = [risk for risk, count in risk_factor_counter.most_common(50)]
                selected_risk_factors = st.multiselect(
                    "Choose risk factors (showing only those in data)",
                    options=common_risks,
                    default=[],
                    key="trend_risk_factors",
                    help=f"Found {len(risk_factor_counter)} unique risk factors in data"
                )
            else:
                st.info("No risk factors found in data")
        
        with col2:
            st.markdown("**🏥 Comorbidities**")
            if comorbidity_counter:
                common_comorbidities = [com for com, count in comorbidity_counter.most_common(50)]
                selected_comorbidities = st.multiselect(
                    "Choose comorbidities (showing only those in data)",
                    options=common_comorbidities,
                    default=[],
                    key="trend_comorbidities",
                    help=f"Found {len(comorbidity_counter)} unique comorbidities in data"
                )
            else:
                st.info("No comorbidities found in data")
    
    # Year range
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        start_year = st.selectbox(
            "Start Year",
            options=list(range(2015, 2026)),  # Exclude 2026
            index=0,
            key="entity_start"
        )
    
    with col2:
        end_year = st.selectbox(
            "End Year",
            options=list(range(2015, 2026)),  # Exclude 2026
            index=10,  # 2025 is index 10 (2015-2025)
            key="entity_end"
        )
    
    # Combine selected entities
    all_entities = []
    entity_types = {}
    
    for lp in selected_lipoproteins:
        all_entities.append(lp)
        entity_types[lp] = "Lipoprotein"
    
    for bio in selected_biomarkers:
        all_entities.append(bio)
        entity_types[bio] = "Biomarker"
    
    for intervention in selected_interventions:
        all_entities.append(intervention)
        entity_types[intervention] = "Intervention"
    
    for drug in selected_drugs:
        all_entities.append(drug)
        entity_types[drug] = "Drug"
    
    for gene in selected_genes:
        all_entities.append(gene)
        entity_types[gene] = "Gene"
    
    for protein in selected_proteins:
        all_entities.append(protein)
        entity_types[protein] = "Protein"
    
    for risk in selected_risk_factors:
        all_entities.append(risk)
        entity_types[risk] = "Risk Factor"
    
    for comorbidity in selected_comorbidities:
        all_entities.append(comorbidity)
        entity_types[comorbidity] = "Comorbidity"
    
    if not all_entities:
        st.info("👆 Select at least one entity from the tabs above to see trends")
        return
    
    # Calculate trends for each entity
    st.markdown("---")
    st.markdown("### 📊 Publication Trends")
    
    entity_data = {}
    years = range(start_year, end_year + 1)
    
    with st.spinner("Analyzing publication trends..."):
        for entity in all_entities:
            entity_data[entity] = {year: 0 for year in years}
            entity_type = entity_types.get(entity, "Unknown")
            
            for pub in all_data:
                year = pub.get('year')
                if not year:
                    continue
                
                try:
                    pub_year = int(year)
                    if pub_year == 2026:  # Explicitly exclude 2026
                        continue
                    if pub_year < start_year or pub_year > end_year:
                        continue
                except:
                    continue
                
                # Check if entity is mentioned
                found = False
                if entity_type == "Lipoprotein":
                    lipoproteins = pub.get('extracted_lipoproteins', [])
                    if isinstance(lipoproteins, list):
                        found = entity in lipoproteins
                    elif lipoproteins == entity:
                        found = True
                elif entity_type == "Biomarker":
                    biomarkers = pub.get('extracted_biomarkers', [])
                    if isinstance(biomarkers, list):
                        found = entity in biomarkers
                    elif biomarkers == entity:
                        found = True
                elif entity_type == "Intervention":
                    interventions = pub.get('extracted_therapeutic_interventions', [])
                    if isinstance(interventions, list):
                        found = entity in interventions
                    elif interventions == entity:
                        found = True
                elif entity_type == "Drug":
                    drugs = pub.get('extracted_drugs', [])
                    if isinstance(drugs, list):
                        for drug in drugs:
                            if isinstance(drug, dict):
                                if entity.lower() in str(drug.get('name', '')).lower():
                                    found = True
                                    break
                            elif entity.lower() in str(drug).lower():
                                found = True
                                break
                    elif drugs:
                        if isinstance(drugs, dict):
                            found = entity.lower() in str(drugs.get('name', '')).lower()
                        else:
                            found = entity.lower() in str(drugs).lower()
                elif entity_type == "Gene":
                    genes = pub.get('extracted_genes', [])
                    if isinstance(genes, list):
                        found = entity in genes
                    elif genes == entity:
                        found = True
                elif entity_type == "Protein":
                    proteins = pub.get('extracted_proteins', [])
                    if isinstance(proteins, list):
                        found = entity in proteins
                    elif proteins == entity:
                        found = True
                elif entity_type == "Risk Factor":
                    risk_factors = pub.get('extracted_risk_factors', [])
                    if isinstance(risk_factors, list):
                        found = entity in risk_factors
                    elif risk_factors == entity:
                        found = True
                elif entity_type == "Comorbidity":
                    comorbidities = pub.get('extracted_comorbidities', [])
                    if isinstance(comorbidities, list):
                        found = entity in comorbidities
                    elif comorbidities == entity:
                        found = True
                
                # Also check in text if not found in structured fields
                if not found:
                    title = (pub.get('title') or '').lower()
                    abstract = (pub.get('abstract') or '').lower()
                    text = f"{title} {abstract}"
                    if entity.lower() in text:
                        found = True
                
                if found:
                    entity_data[entity][pub_year] += 1
    
    # Create DataFrame
    df_trends = pd.DataFrame(entity_data).T
    df_trends = df_trends.fillna(0).astype(int)
    
    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_pubs = df_trends.sum().sum()
        st.metric("📚 Total Publications", f"{total_pubs:,}")
    
    with col2:
        most_popular = df_trends.sum(axis=1).idxmax() if not df_trends.empty else "N/A"
        st.metric("🏆 Most Popular", most_popular)
    
    with col3:
        avg_per_entity = df_trends.sum(axis=1).mean() if not df_trends.empty else 0
        st.metric("📊 Avg per Entity", f"{avg_per_entity:.0f}")
    
    with col4:
        peak_year = df_trends.sum(axis=0).idxmax() if not df_trends.empty else "N/A"
        st.metric("📅 Peak Year", peak_year)
    
    # 1. Line Chart - All entities
    st.markdown("#### 📈 Comparative Trend Lines")
    
    df_plot = df_trends.T
    df_plot.index = df_plot.index.astype(int)
    
    fig = go.Figure()
    
    colors = px.colors.qualitative.Set3
    for i, entity in enumerate(all_entities):
        entity_type = entity_types.get(entity, "Unknown")
        fig.add_trace(go.Scatter(
            x=df_plot.index,
            y=df_plot[entity],
            mode='lines+markers',
            name=f"{entity} ({entity_type})",
            line=dict(width=3),
            marker=dict(size=8),
            hovertemplate=f"<b>{entity}</b><br>Year: %{{x}}<br>Publications: %{{y}}<extra></extra>"
        ))
    
    fig.update_layout(
        title=f"Publication Trends ({start_year}-{end_year})",
        xaxis_title="Year",
        yaxis_title="Number of Publications",
        hovermode='x unified',
        height=500,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 2. Stacked Area Chart
    st.markdown("#### 📊 Stacked Area Chart")
    
    fig = go.Figure()
    
    for i, entity in enumerate(all_entities):
        fig.add_trace(go.Scatter(
            x=df_plot.index,
            y=df_plot[entity],
            mode='lines',
            name=entity,
            stackgroup='one',
            fillcolor=colors[i % len(colors)],
            hovertemplate=f"<b>{entity}</b><br>Year: %{{x}}<br>Publications: %{{y}}<extra></extra>"
        ))
    
    fig.update_layout(
        title=f"Cumulative Research Contribution",
        xaxis_title="Year",
        yaxis_title="Publications (Stacked)",
        hovermode='x unified',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_publications_page(all_data):
    """Render publications browse page"""
    st.header("📖 Browse Publications")
    
    # Pagination
    items_per_page = st.select_slider(
        "Publications per page",
        options=[10, 25, 50, 100],
        value=25
    )
    
    total_pages = (len(all_data) - 1) // items_per_page + 1
    page = st.number_input(
        f"Page (1 to {total_pages})",
        min_value=1,
        max_value=total_pages,
        value=1
    )
    
    # Calculate slice
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    
    # Display publications
    st.info(f"Showing {start_idx + 1}-{min(end_idx, len(all_data))} of {len(all_data)} publications")
    
    for i, pub in enumerate(all_data[start_idx:end_idx], start_idx + 1):
        with st.expander(f"📄 {i}. {pub.get('title') or 'No title'}"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**PMID:** {pub.get('pmid') or 'N/A'}")
                st.markdown(f"**Year:** {pub.get('year') or 'N/A'}")
                st.markdown(f"**Journal:** {pub.get('journal') or 'N/A'}")
            
            with col2:
                if pub.get('pmid'):
                    st.link_button(
                        "PubMed →",
                        f"https://pubmed.ncbi.nlm.nih.gov/{pub['pmid']}/"
                    )
            
            abstract = pub.get('abstract')
            if abstract:
                st.markdown("**Abstract:**")
                st.text(abstract[:1000] + "..." if len(abstract) > 1000 else abstract)


@st.cache_data
def process_correlations_data(all_data):
    """Process and extract correlations data with caching"""
    all_correlations = []
    for pub in all_data:
        correlations = pub.get('extracted_correlations', [])
        if correlations:
            if isinstance(correlations, list):
                # Filter out None, empty strings, and ensure all are strings
                for corr in correlations:
                    if corr and isinstance(corr, str) and corr.strip():
                        # Clean and truncate very long strings early
                        cleaned = corr.strip()[:500]  # Limit to 500 chars max
                        all_correlations.append(cleaned)
            elif isinstance(correlations, str) and correlations.strip():
                cleaned = correlations.strip()[:500]
                all_correlations.append(cleaned)
    return all_correlations


def render_field_analysis_page(all_data):
    """Render comprehensive field analysis page with word clouds and statistics"""
    st.header("📊 Field Analysis & Correlations")
    
    st.markdown("""
    **Comprehensive Analysis of All Extracted Fields**  
    *Visualize correlations, entities, and patterns across all publications*
    """)
    
    # Field definitions
    field_labels = {
        'extracted_lipoproteins': '🧬 Lipoproteins',
        'extracted_biomarkers': '🔬 Biomarkers',
        'extracted_genes': '🧪 Genes',
        'extracted_proteins': '⚛️ Proteins',
        'extracted_drugs': '💊 Drugs',
        'extracted_therapeutic_interventions': '💉 Therapeutic Interventions',
        'extracted_risk_factors': '⚠️ Risk Factors',
        'extracted_comorbidities': '🏥 Comorbidities',
        'extracted_pathophysiology': '🔬 Pathophysiology',
        'extracted_clinical_outcomes': '📈 Clinical Outcomes',
        'extracted_thematic_categories': '📚 Thematic Categories',
        'extracted_correlations': '🔗 Correlations'
    }
    
    # Calculate statistics for all fields
    st.markdown("---")
    st.subheader("📈 Field Statistics")
    
    field_stats = {}
    for field, label in field_labels.items():
        count = 0
        total_items = 0
        for pub in all_data:
            values = pub.get(field, [])
            if values:
                if isinstance(values, list):
                    if len(values) > 0:
                        count += 1
                        total_items += len(values)
                else:
                    count += 1
                    total_items += 1
        
        field_stats[field] = {
            'label': label,
            'publications_with_data': count,
            'total_items': total_items,
            'avg_per_publication': total_items / count if count > 0 else 0,
            'coverage_pct': (count / len(all_data) * 100) if len(all_data) > 0 else 0
        }
    
    # Display statistics in columns
    cols = st.columns(3)
    for idx, (field, stats) in enumerate(field_stats.items()):
        col = cols[idx % 3]
        with col:
            st.metric(
                label=stats['label'],
                value=f"{stats['publications_with_data']:,}",
                delta=f"{stats['coverage_pct']:.1f}% coverage"
            )
            st.caption(f"Total items: {stats['total_items']:,} | Avg: {stats['avg_per_publication']:.1f}")
    
    st.markdown("---")
    
    # CORRELATIONS VISUALIZATION
    st.subheader("🔗 Correlations Analysis")
    st.markdown("Key relationships and associations extracted from publications")
    
    # Collect all correlations using cached function
    all_correlations = process_correlations_data(all_data)
    
    if all_correlations:
        # Statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Correlations", f"{len(all_correlations):,}")
        with col2:
            st.metric("Publications with Correlations", 
                     f"{sum(1 for p in all_data if p.get('extracted_correlations')):,}")
        with col3:
            unique_correlations = len(set(all_correlations))
            st.metric("Unique Correlations", f"{unique_correlations:,}")
        with col4:
            avg_per_pub = len(all_correlations) / sum(1 for p in all_data if p.get('extracted_correlations')) if sum(1 for p in all_data if p.get('extracted_correlations')) > 0 else 0
            st.metric("Avg per Publication", f"{avg_per_pub:.1f}")
        
        st.markdown("---")
        
        # Create tabs for different correlation visualizations
        corr_tab1, corr_tab2, corr_tab3 = st.tabs([
            "📊 Top Correlations",
            "☁️ Word Cloud (Key Terms)",
            "🔍 Search & Filter"
        ])
        
        with corr_tab1:
            st.markdown("#### Most Frequently Mentioned Correlations")
            
            correlation_counter = Counter(all_correlations)
            top_correlations = correlation_counter.most_common(50)
            
            if top_correlations:
                # Create DataFrame for better visualization
                # Truncate long correlation strings to prevent rendering issues
                df_data = []
                for corr, freq in top_correlations:
                    # Ensure string is clean and properly encoded
                    if not isinstance(corr, str):
                        corr = str(corr)
                    # Remove any problematic characters and truncate
                    corr_clean = corr.encode('ascii', 'ignore').decode('ascii')[:150]
                    display_corr = corr_clean + ('...' if len(corr) > 150 else '')
                    df_data.append({
                        'Correlation': display_corr,
                        'Full Correlation': corr[:300],  # Limit full text too
                        'Frequency': freq
                    })
                
                df_corr = pd.DataFrame(df_data)
                
                # Use st.table instead of st.dataframe for better stability
                # Limit to top 30 for display to prevent React issues
                df_display = df_corr.head(30)[['Correlation', 'Frequency']].copy()
                
                # Display as static table (more stable than interactive dataframe)
                try:
                    st.table(df_display)
                except Exception:
                    # Fallback if pyarrow is not available
                    st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)
                
                if len(df_corr) > 30:
                    st.caption(f"Showing top 30 of {len(df_corr)} correlations. Use search tab to find more.")
                
                # Also show as bar chart for top 15 (reduced from 20 for stability)
                st.markdown("#### Top 15 Correlations (Bar Chart)")
                df_top15 = df_corr.head(15).copy()
                
                # Truncate correlation strings for y-axis labels (max 80 chars for chart)
                df_top15['Correlation_Short'] = df_top15['Correlation'].apply(
                    lambda x: (x[:80] + '...') if len(x) > 80 else x
                )
                
                try:
                    # Create a simpler chart with truncated labels to prevent rendering issues
                    fig = px.bar(
                        df_top15, 
                        x='Frequency', 
                        y='Correlation_Short',  # Use shortened version for y-axis
                        orientation='h',
                        title='Top 15 Most Frequent Correlations',
                        color='Frequency',
                        color_continuous_scale='Reds',
                        labels={'Frequency': 'Number of Mentions', 'Correlation_Short': 'Correlation Statement'}
                    )
                    fig.update_layout(
                        height=600,  # Reduced height
                        yaxis={'categoryorder': 'total ascending'},
                        yaxis_title='Correlation Statement',
                        margin=dict(l=10, r=10, t=50, b=10)
                    )
                    # Simplified hover text
                    fig.update_traces(
                        hovertemplate='<b>%{y}</b><br>Frequency: %{x}<extra></extra>'
                    )
                    st.plotly_chart(fig, use_container_width=True, key="corr_chart")
                except Exception as e:
                    st.error(f"Error rendering chart: {e}")
                    st.info("Displaying data in table format instead")
                    try:
                        st.table(df_top15[['Correlation', 'Frequency']])
                    except Exception:
                        # Fallback if pyarrow is not available
                        st.write(df_top15[['Correlation', 'Frequency']].to_html(escape=False, index=False), unsafe_allow_html=True)
        
        with corr_tab2:
            st.markdown("#### Word Cloud of Key Terms from Correlations")
            st.markdown("*Extracted important medical terms and relationships*")
            
            if WORDCLOUD_AVAILABLE:
                try:
                    # Process correlations to extract key terms
                    # Remove common stop words and focus on medical/biological terms
                    stop_words = {
                        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                        'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be', 
                        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 
                        'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 
                        'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their', 'there',
                        'associated', 'correlates', 'correlated', 'linked', 'related', 'with',
                        'increased', 'decreased', 'higher', 'lower', 'reduced', 'reduces'
                    }
                    
                    # Extract meaningful terms from correlations
                    processed_terms = []
                    for corr in all_correlations:
                        # Split into words and filter
                        words = re.findall(r'\b[a-zA-Z]{3,}\b', corr.lower())
                        # Filter out stop words and keep medical/biological terms
                        meaningful = [w for w in words if w not in stop_words and len(w) > 3]
                        processed_terms.extend(meaningful)
                    
                    if processed_terms:
                        # Count term frequencies
                        term_counter = Counter(processed_terms)
                        # Create text with frequencies
                        term_text = ' '.join([f"{term} " * min(count, 10) for term, count in term_counter.most_common(100)])
                        
                        # Generate improved word cloud
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            wordcloud = WordCloud(
                                width=1000,
                                height=500,
                                background_color='white',
                                colormap='Reds',
                                max_words=80,
                                relative_scaling=0.4,
                                collocations=False,
                                min_font_size=10,
                                max_font_size=120,
                                prefer_horizontal=0.7
                            ).generate(term_text)
                            
                            fig, ax = plt.subplots(figsize=(14, 7))
                            ax.imshow(wordcloud, interpolation='bilinear')
                            ax.axis('off')
                            plt.tight_layout(pad=0)
                            st.pyplot(fig)
                            plt.close(fig)
                        
                        with col2:
                            st.markdown("**Top Key Terms:**")
                            for term, count in term_counter.most_common(15):
                                st.caption(f"• **{term}** ({count})")
                    else:
                        st.info("Could not extract meaningful terms from correlations")
                        
                except Exception as e:
                    st.error(f"Error generating word cloud: {e}")
                    st.info("Showing raw correlation text instead")
                    st.text_area("Sample Correlations", '\n'.join(all_correlations[:30]), height=300)
            else:
                st.warning("WordCloud library not available. Install with: `pip install wordcloud matplotlib`")
        
        with corr_tab3:
            st.markdown("#### Search and Filter Correlations")
            
            # Search box
            search_term = st.text_input(
                "Search correlations by keyword",
                placeholder="e.g., LDL, atherosclerosis, risk, PCSK9..."
            )
            
            # Filter by keyword
            filtered_correlations = all_correlations
            if search_term:
                search_lower = search_term.lower()
                filtered_correlations = [c for c in all_correlations if search_lower in c.lower()]
                st.info(f"Found {len(filtered_correlations)} correlations containing '{search_term}'")
            
            # Display filtered results
            if filtered_correlations:
                # Group by frequency
                filtered_counter = Counter(filtered_correlations)
                filtered_sorted = sorted(filtered_counter.items(), key=lambda x: x[1], reverse=True)
                
                # Show top results
                num_results = st.slider("Number of results to show", 10, min(100, len(filtered_sorted)), 30)
                
                for i, (corr, count) in enumerate(filtered_sorted[:num_results], 1):
                    with st.expander(f"#{i} ({count} mention{'s' if count > 1 else ''}) - {corr[:80]}..."):
                        st.markdown(f"**Full correlation:** {corr}")
                        if count > 1:
                            st.caption(f"📊 Mentioned {count} times across publications")
            else:
                st.warning("No correlations found matching your search")
    else:
        st.info("No correlations found in the dataset")
    
    st.markdown("---")
    
    # FIELD-SPECIFIC VISUALIZATIONS
    st.subheader("📊 Field-Specific Visualizations")
    
    # Create tabs for different field groups
    tab1, tab2, tab3, tab4 = st.tabs([
        "🧬 Lipoproteins & Biomarkers",
        "🧪 Genes & Proteins",
        "💊 Drugs & Interventions",
        "⚠️ Risk Factors & Outcomes"
    ])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🧬 Top Lipoproteins")
            lipoprotein_counter = Counter()
            for pub in all_data:
                lipoproteins = pub.get('extracted_lipoproteins', [])
                if isinstance(lipoproteins, list):
                    lipoprotein_counter.update(lipoproteins)
                elif lipoproteins:
                    lipoprotein_counter[lipoproteins] += 1
            
            if lipoprotein_counter:
                top_lp = lipoprotein_counter.most_common(15)
                df_lp = pd.DataFrame(top_lp, columns=['Lipoprotein', 'Count'])
                fig = px.bar(df_lp, x='Count', y='Lipoprotein', orientation='h',
                            title='Top 15 Lipoproteins',
                            color='Count', color_continuous_scale='Reds')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No lipoprotein data")
        
        with col2:
            st.markdown("#### 🔬 Top Biomarkers")
            biomarker_counter = Counter()
            for pub in all_data:
                biomarkers = pub.get('extracted_biomarkers', [])
                if isinstance(biomarkers, list):
                    biomarker_counter.update(biomarkers)
                elif biomarkers:
                    biomarker_counter[biomarkers] += 1
            
            if biomarker_counter:
                top_bio = biomarker_counter.most_common(15)
                df_bio = pd.DataFrame(top_bio, columns=['Biomarker', 'Count'])
                fig = px.bar(df_bio, x='Count', y='Biomarker', orientation='h',
                            title='Top 15 Biomarkers',
                            color='Count', color_continuous_scale='Blues')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No biomarker data")
    
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🧪 Top Genes")
            gene_counter = Counter()
            for pub in all_data:
                genes = pub.get('extracted_genes', [])
                if isinstance(genes, list):
                    gene_counter.update(genes)
                elif genes:
                    gene_counter[genes] += 1
            
            if gene_counter:
                top_genes = gene_counter.most_common(15)
                df_genes = pd.DataFrame(top_genes, columns=['Gene', 'Count'])
                fig = px.bar(df_genes, x='Count', y='Gene', orientation='h',
                            title='Top 15 Genes',
                            color='Count', color_continuous_scale='Greens')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No gene data")
        
        with col2:
            st.markdown("#### ⚛️ Top Proteins")
            protein_counter = Counter()
            for pub in all_data:
                proteins = pub.get('extracted_proteins', [])
                if isinstance(proteins, list):
                    protein_counter.update(proteins)
                elif proteins:
                    protein_counter[proteins] += 1
            
            if protein_counter:
                top_proteins = protein_counter.most_common(15)
                df_proteins = pd.DataFrame(top_proteins, columns=['Protein', 'Count'])
                fig = px.bar(df_proteins, x='Count', y='Protein', orientation='h',
                            title='Top 15 Proteins',
                            color='Count', color_continuous_scale='Purples')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No protein data")
    
    with tab3:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 💊 Top Drugs")
            drug_counter = Counter()
            for pub in all_data:
                drugs = pub.get('extracted_drugs', [])
                if isinstance(drugs, list):
                    for drug in drugs:
                        if isinstance(drug, dict):
                            drug_counter[drug.get('name', drug)] += 1
                        else:
                            drug_counter[drug] += 1
                elif drugs:
                    drug_counter[drugs] += 1
            
            if drug_counter:
                top_drugs = drug_counter.most_common(15)
                df_drugs = pd.DataFrame(top_drugs, columns=['Drug', 'Count'])
                fig = px.bar(df_drugs, x='Count', y='Drug', orientation='h',
                            title='Top 15 Drugs',
                            color='Count', color_continuous_scale='Oranges')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No drug data")
        
        with col2:
            st.markdown("#### 💉 Top Therapeutic Interventions")
            intervention_counter = Counter()
            for pub in all_data:
                interventions = pub.get('extracted_therapeutic_interventions', [])
                if isinstance(interventions, list):
                    intervention_counter.update(interventions)
                elif interventions:
                    intervention_counter[interventions] += 1
            
            if intervention_counter:
                top_int = intervention_counter.most_common(15)
                df_int = pd.DataFrame(top_int, columns=['Intervention', 'Count'])
                fig = px.bar(df_int, x='Count', y='Intervention', orientation='h',
                            title='Top 15 Interventions',
                            color='Count', color_continuous_scale='YlOrRd')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No intervention data")
    
    with tab4:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### ⚠️ Top Risk Factors")
            risk_counter = Counter()
            for pub in all_data:
                risks = pub.get('extracted_risk_factors', [])
                if isinstance(risks, list):
                    risk_counter.update(risks)
                elif risks:
                    risk_counter[risks] += 1
            
            if risk_counter:
                top_risks = risk_counter.most_common(15)
                df_risks = pd.DataFrame(top_risks, columns=['Risk Factor', 'Count'])
                fig = px.bar(df_risks, x='Count', y='Risk Factor', orientation='h',
                            title='Top 15 Risk Factors',
                            color='Count', color_continuous_scale='Reds')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No risk factor data")
        
        with col2:
            st.markdown("#### 📈 Top Clinical Outcomes")
            outcome_counter = Counter()
            for pub in all_data:
                outcomes = pub.get('extracted_clinical_outcomes', [])
                if isinstance(outcomes, list):
                    outcome_counter.update(outcomes)
                elif outcomes:
                    outcome_counter[outcomes] += 1
            
            if outcome_counter:
                top_outcomes = outcome_counter.most_common(15)
                df_outcomes = pd.DataFrame(top_outcomes, columns=['Outcome', 'Count'])
                fig = px.bar(df_outcomes, x='Count', y='Outcome', orientation='h',
                            title='Top 15 Clinical Outcomes',
                            color='Count', color_continuous_scale='Blues')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No outcome data")
    
    # HISTOGRAMS - Distribution of items per publication
    st.markdown("---")
    st.subheader("📊 Histograms: Distribution of Items per Publication")
    st.markdown("Shows how many items of each type are typically found per publication")
    
    # Prepare histogram data
    histogram_fields = {
        'extracted_lipoproteins': '🧬 Lipoproteins per Publication',
        'extracted_biomarkers': '🔬 Biomarkers per Publication',
        'extracted_genes': '🧪 Genes per Publication',
        'extracted_proteins': '⚛️ Proteins per Publication',
        'extracted_drugs': '💊 Drugs per Publication',
        'extracted_therapeutic_interventions': '💉 Interventions per Publication',
        'extracted_risk_factors': '⚠️ Risk Factors per Publication',
        'extracted_comorbidities': '🏥 Comorbidities per Publication',
        'extracted_pathophysiology': '🔬 Pathophysiology Terms per Publication',
        'extracted_clinical_outcomes': '📈 Clinical Outcomes per Publication',
        'extracted_thematic_categories': '📚 Categories per Publication',
        'extracted_correlations': '🔗 Correlations per Publication'
    }
    
    # Create histogram tabs
    hist_tab1, hist_tab2, hist_tab3 = st.tabs([
        "🧬 Lipoproteins & Biomarkers",
        "💊 Drugs & Interventions", 
        "⚠️ Risk Factors & Others"
    ])
    
    with hist_tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🧬 Lipoproteins per Publication")
            lp_counts = []
            for pub in all_data:
                lipoproteins = pub.get('extracted_lipoproteins', [])
                if isinstance(lipoproteins, list):
                    lp_counts.append(len(lipoproteins))
                elif lipoproteins:
                    lp_counts.append(1)
                else:
                    lp_counts.append(0)
            
            if any(lp_counts):
                df_lp_hist = pd.DataFrame({'Count': lp_counts})
                fig = px.histogram(df_lp_hist, x='Count', nbins=20,
                                  title='Distribution of Lipoproteins per Publication',
                                  labels={'Count': 'Number of Lipoproteins', 'count': 'Number of Publications'},
                                  color_discrete_sequence=['#d32f2f'])
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch')
                st.caption(f"Mean: {pd.Series(lp_counts).mean():.1f} | Median: {pd.Series(lp_counts).median():.1f} | Max: {max(lp_counts)}")
            else:
                st.info("No lipoprotein data")
        
        with col2:
            st.markdown("#### 🔬 Biomarkers per Publication")
            bio_counts = []
            for pub in all_data:
                biomarkers = pub.get('extracted_biomarkers', [])
                if isinstance(biomarkers, list):
                    bio_counts.append(len(biomarkers))
                elif biomarkers:
                    bio_counts.append(1)
                else:
                    bio_counts.append(0)
            
            if any(bio_counts):
                df_bio_hist = pd.DataFrame({'Count': bio_counts})
                fig = px.histogram(df_bio_hist, x='Count', nbins=20,
                                  title='Distribution of Biomarkers per Publication',
                                  labels={'Count': 'Number of Biomarkers', 'count': 'Number of Publications'},
                                  color_discrete_sequence=['#1976d2'])
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch')
                st.caption(f"Mean: {pd.Series(bio_counts).mean():.1f} | Median: {pd.Series(bio_counts).median():.1f} | Max: {max(bio_counts)}")
            else:
                st.info("No biomarker data")
        
        # Genes and Proteins
        col3, col4 = st.columns(2)
        
        with col3:
            st.markdown("#### 🧪 Genes per Publication")
            gene_counts = []
            for pub in all_data:
                genes = pub.get('extracted_genes', [])
                if isinstance(genes, list):
                    gene_counts.append(len(genes))
                elif genes:
                    gene_counts.append(1)
                else:
                    gene_counts.append(0)
            
            if any(gene_counts):
                df_gene_hist = pd.DataFrame({'Count': gene_counts})
                fig = px.histogram(df_gene_hist, x='Count', nbins=20,
                                  title='Distribution of Genes per Publication',
                                  labels={'Count': 'Number of Genes', 'count': 'Number of Publications'},
                                  color_discrete_sequence=['#388e3c'])
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch')
                st.caption(f"Mean: {pd.Series(gene_counts).mean():.1f} | Median: {pd.Series(gene_counts).median():.1f} | Max: {max(gene_counts)}")
            else:
                st.info("No gene data")
        
        with col4:
            st.markdown("#### ⚛️ Proteins per Publication")
            protein_counts = []
            for pub in all_data:
                proteins = pub.get('extracted_proteins', [])
                if isinstance(proteins, list):
                    protein_counts.append(len(proteins))
                elif proteins:
                    protein_counts.append(1)
                else:
                    protein_counts.append(0)
            
            if any(protein_counts):
                df_protein_hist = pd.DataFrame({'Count': protein_counts})
                fig = px.histogram(df_protein_hist, x='Count', nbins=20,
                                  title='Distribution of Proteins per Publication',
                                  labels={'Count': 'Number of Proteins', 'count': 'Number of Publications'},
                                  color_discrete_sequence=['#7b1fa2'])
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch')
                st.caption(f"Mean: {pd.Series(protein_counts).mean():.1f} | Median: {pd.Series(protein_counts).median():.1f} | Max: {max(protein_counts)}")
            else:
                st.info("No protein data")
    
    with hist_tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 💊 Drugs per Publication")
            drug_counts = []
            for pub in all_data:
                drugs = pub.get('extracted_drugs', [])
                if isinstance(drugs, list):
                    drug_counts.append(len(drugs))
                elif drugs:
                    drug_counts.append(1)
                else:
                    drug_counts.append(0)
            
            if any(drug_counts):
                df_drug_hist = pd.DataFrame({'Count': drug_counts})
                fig = px.histogram(df_drug_hist, x='Count', nbins=20,
                                  title='Distribution of Drugs per Publication',
                                  labels={'Count': 'Number of Drugs', 'count': 'Number of Publications'},
                                  color_discrete_sequence=['#f57c00'])
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch')
                st.caption(f"Mean: {pd.Series(drug_counts).mean():.1f} | Median: {pd.Series(drug_counts).median():.1f} | Max: {max(drug_counts)}")
            else:
                st.info("No drug data")
        
        with col2:
            st.markdown("#### 💉 Interventions per Publication")
            intervention_counts = []
            for pub in all_data:
                interventions = pub.get('extracted_therapeutic_interventions', [])
                if isinstance(interventions, list):
                    intervention_counts.append(len(interventions))
                elif interventions:
                    intervention_counts.append(1)
                else:
                    intervention_counts.append(0)
            
            if any(intervention_counts):
                df_int_hist = pd.DataFrame({'Count': intervention_counts})
                fig = px.histogram(df_int_hist, x='Count', nbins=20,
                                  title='Distribution of Interventions per Publication',
                                  labels={'Count': 'Number of Interventions', 'count': 'Number of Publications'},
                                  color_discrete_sequence=['#c62828'])
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch')
                st.caption(f"Mean: {pd.Series(intervention_counts).mean():.1f} | Median: {pd.Series(intervention_counts).median():.1f} | Max: {max(intervention_counts)}")
            else:
                st.info("No intervention data")
    
    with hist_tab3:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### ⚠️ Risk Factors per Publication")
            risk_counts = []
            for pub in all_data:
                risks = pub.get('extracted_risk_factors', [])
                if isinstance(risks, list):
                    risk_counts.append(len(risks))
                elif risks:
                    risk_counts.append(1)
                else:
                    risk_counts.append(0)
            
            if any(risk_counts):
                df_risk_hist = pd.DataFrame({'Count': risk_counts})
                fig = px.histogram(df_risk_hist, x='Count', nbins=20,
                                  title='Distribution of Risk Factors per Publication',
                                  labels={'Count': 'Number of Risk Factors', 'count': 'Number of Publications'},
                                  color_discrete_sequence=['#e64a19'])
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch')
                st.caption(f"Mean: {pd.Series(risk_counts).mean():.1f} | Median: {pd.Series(risk_counts).median():.1f} | Max: {max(risk_counts)}")
            else:
                st.info("No risk factor data")
        
        with col2:
            st.markdown("#### 🏥 Comorbidities per Publication")
            comorbidity_counts = []
            for pub in all_data:
                comorbidities = pub.get('extracted_comorbidities', [])
                if isinstance(comorbidities, list):
                    comorbidity_counts.append(len(comorbidities))
                elif comorbidities:
                    comorbidity_counts.append(1)
                else:
                    comorbidity_counts.append(0)
            
            if any(comorbidity_counts):
                df_com_hist = pd.DataFrame({'Count': comorbidity_counts})
                fig = px.histogram(df_com_hist, x='Count', nbins=20,
                                  title='Distribution of Comorbidities per Publication',
                                  labels={'Count': 'Number of Comorbidities', 'count': 'Number of Publications'},
                                  color_discrete_sequence=['#5d4037'])
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch')
                st.caption(f"Mean: {pd.Series(comorbidity_counts).mean():.1f} | Median: {pd.Series(comorbidity_counts).median():.1f} | Max: {max(comorbidity_counts)}")
            else:
                st.info("No comorbidity data")
        
        # Additional histograms
        col3, col4 = st.columns(2)
        
        with col3:
            st.markdown("#### 🔗 Correlations per Publication")
            corr_counts = []
            for pub in all_data:
                correlations = pub.get('extracted_correlations', [])
                if isinstance(correlations, list):
                    corr_counts.append(len(correlations))
                elif correlations:
                    corr_counts.append(1)
                else:
                    corr_counts.append(0)
            
            if any(corr_counts):
                df_corr_hist = pd.DataFrame({'Count': corr_counts})
                fig = px.histogram(df_corr_hist, x='Count', nbins=20,
                                  title='Distribution of Correlations per Publication',
                                  labels={'Count': 'Number of Correlations', 'count': 'Number of Publications'},
                                  color_discrete_sequence=['#c2185b'])
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch')
                st.caption(f"Mean: {pd.Series(corr_counts).mean():.1f} | Median: {pd.Series(corr_counts).median():.1f} | Max: {max(corr_counts)}")
            else:
                st.info("No correlation data")
        
        with col4:
            st.markdown("#### 📈 Clinical Outcomes per Publication")
            outcome_counts = []
            for pub in all_data:
                outcomes = pub.get('extracted_clinical_outcomes', [])
                if isinstance(outcomes, list):
                    outcome_counts.append(len(outcomes))
                elif outcomes:
                    outcome_counts.append(1)
                else:
                    outcome_counts.append(0)
            
            if any(outcome_counts):
                df_outcome_hist = pd.DataFrame({'Count': outcome_counts})
                fig = px.histogram(df_outcome_hist, x='Count', nbins=20,
                                  title='Distribution of Clinical Outcomes per Publication',
                                  labels={'Count': 'Number of Outcomes', 'count': 'Number of Publications'},
                                  color_discrete_sequence=['#0277bd'])
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch')
                st.caption(f"Mean: {pd.Series(outcome_counts).mean():.1f} | Median: {pd.Series(outcome_counts).median():.1f} | Max: {max(outcome_counts)}")
            else:
                st.info("No outcome data")
    
    # Additional visualizations
    st.markdown("---")
    st.subheader("📚 Additional Field Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🏥 Comorbidities")
        comorbidity_counter = Counter()
        for pub in all_data:
            comorbidities = pub.get('extracted_comorbidities', [])
            if isinstance(comorbidities, list):
                comorbidity_counter.update(comorbidities)
            elif comorbidities:
                comorbidity_counter[comorbidities] += 1
        
        if comorbidity_counter:
            top_com = comorbidity_counter.most_common(10)
            df_com = pd.DataFrame(top_com, columns=['Comorbidity', 'Count'])
            fig = px.pie(df_com, values='Count', names='Comorbidity',
                        title='Top 10 Comorbidities')
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No comorbidity data")
    
    with col2:
        st.markdown("#### 📚 Thematic Categories")
        category_counter = Counter()
        for pub in all_data:
            categories = pub.get('extracted_thematic_categories', [])
            if isinstance(categories, list):
                category_counter.update(categories)
            elif categories:
                category_counter[categories] += 1
        
        if category_counter:
            top_cat = category_counter.most_common(10)
            df_cat = pd.DataFrame(top_cat, columns=['Category', 'Count'])
            fig = px.pie(df_cat, values='Count', names='Category',
                        title='Top 10 Thematic Categories')
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No category data")
    
    # Pathophysiology visualization
    st.markdown("#### 🔬 Top Pathophysiology Terms")
    patho_counter = Counter()
    for pub in all_data:
        patho = pub.get('extracted_pathophysiology', [])
        if isinstance(patho, list):
            patho_counter.update(patho)
        elif patho:
            patho_counter[patho] += 1
    
    if patho_counter:
        top_patho = patho_counter.most_common(20)
        df_patho = pd.DataFrame(top_patho, columns=['Pathophysiology', 'Count'])
        fig = px.bar(df_patho, x='Count', y='Pathophysiology', orientation='h',
                    title='Top 20 Pathophysiology Terms',
                    color='Count', color_continuous_scale='Viridis')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No pathophysiology data")
    
    # Export correlations
    st.markdown("---")
    if st.button("📥 Export All Correlations"):
        all_correlations_export = []
        for pub in all_data:
            correlations = pub.get('extracted_correlations', [])
            if correlations:
                if isinstance(correlations, list):
                    for corr in correlations:
                        all_correlations_export.append({
                            'pmid': pub.get('pmid', ''),
                            'title': pub.get('title', ''),
                            'correlation': corr
                        })
                else:
                    all_correlations_export.append({
                        'pmid': pub.get('pmid', ''),
                        'title': pub.get('title', ''),
                        'correlation': correlations
                    })
        
        if all_correlations_export:
            df_corr = pd.DataFrame(all_correlations_export)
            csv = df_corr.to_csv(index=False)
            st.download_button(
                label="📥 Download Correlations CSV",
                data=csv,
                file_name=f"athero_correlations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )


def render_wordclouds_page(all_data):
    """Render word clouds page with category-specific visualizations"""
    st.header("☁️ Word Clouds by Category")
    
    st.markdown("""
    **Visual representation of the most common entities in each category**  
    *Larger text = more frequent mentions across publications*
    """)
    
    if not WORDCLOUD_AVAILABLE:
        st.warning("⚠️ WordCloud library not available. Install with: `pip install wordcloud matplotlib`")
        return
    
    # Collect data for all categories
    category_data = {
        '💊 Drugs': Counter(),
        '🧬 Lipoproteins': Counter(),
        '🔬 Biomarkers': Counter(),
        '🧪 Genes': Counter(),
        '⚛️ Proteins': Counter(),
        '💉 Therapeutic Interventions': Counter(),
        '⚠️ Risk Factors': Counter(),
        '🏥 Comorbidities': Counter(),
        '🔬 Pathophysiology': Counter(),
        '📈 Clinical Outcomes': Counter()
    }
    
    with st.spinner("Collecting data from publications..."):
        for pub in all_data:
            # Drugs
            drugs = pub.get('extracted_drugs', [])
            if isinstance(drugs, list):
                for drug in drugs:
                    if isinstance(drug, dict):
                        category_data['💊 Drugs'][drug.get('name', drug)] += 1
                    else:
                        category_data['💊 Drugs'][drug] += 1
            elif drugs:
                if isinstance(drugs, dict):
                    category_data['💊 Drugs'][drugs.get('name', drugs)] += 1
                else:
                    category_data['💊 Drugs'][drugs] += 1
            
            # Lipoproteins
            lipoproteins = pub.get('extracted_lipoproteins', [])
            if isinstance(lipoproteins, list):
                category_data['🧬 Lipoproteins'].update(lipoproteins)
            elif lipoproteins:
                category_data['🧬 Lipoproteins'][lipoproteins] += 1
            
            # Biomarkers
            biomarkers = pub.get('extracted_biomarkers', [])
            if isinstance(biomarkers, list):
                category_data['🔬 Biomarkers'].update(biomarkers)
            elif biomarkers:
                category_data['🔬 Biomarkers'][biomarkers] += 1
            
            # Genes
            genes = pub.get('extracted_genes', [])
            if isinstance(genes, list):
                category_data['🧪 Genes'].update(genes)
            elif genes:
                category_data['🧪 Genes'][genes] += 1
            
            # Proteins
            proteins = pub.get('extracted_proteins', [])
            if isinstance(proteins, list):
                category_data['⚛️ Proteins'].update(proteins)
            elif proteins:
                category_data['⚛️ Proteins'][proteins] += 1
            
            # Therapeutic Interventions
            interventions = pub.get('extracted_therapeutic_interventions', [])
            if isinstance(interventions, list):
                category_data['💉 Therapeutic Interventions'].update(interventions)
            elif interventions:
                category_data['💉 Therapeutic Interventions'][interventions] += 1
            
            # Risk Factors
            risk_factors = pub.get('extracted_risk_factors', [])
            if isinstance(risk_factors, list):
                category_data['⚠️ Risk Factors'].update(risk_factors)
            elif risk_factors:
                category_data['⚠️ Risk Factors'][risk_factors] += 1
            
            # Comorbidities
            comorbidities = pub.get('extracted_comorbidities', [])
            if isinstance(comorbidities, list):
                category_data['🏥 Comorbidities'].update(comorbidities)
            elif comorbidities:
                category_data['🏥 Comorbidities'][comorbidities] += 1
            
            # Pathophysiology
            pathophysiology = pub.get('extracted_pathophysiology', [])
            if isinstance(pathophysiology, list):
                category_data['🔬 Pathophysiology'].update(pathophysiology)
            elif pathophysiology:
                category_data['🔬 Pathophysiology'][pathophysiology] += 1
            
            # Clinical Outcomes
            outcomes = pub.get('extracted_clinical_outcomes', [])
            if isinstance(outcomes, list):
                category_data['📈 Clinical Outcomes'].update(outcomes)
            elif outcomes:
                category_data['📈 Clinical Outcomes'][outcomes] += 1
    
    # Filter out empty categories
    active_categories = {k: v for k, v in category_data.items() if len(v) > 0}
    
    if not active_categories:
        st.warning("⚠️ No data available for word clouds. Make sure publications have extracted fields.")
        return
    
    # Category selection
    st.markdown("### 🎯 Select Category")
    selected_category = st.selectbox(
        "Choose a category to visualize:",
        options=list(active_categories.keys()),
        index=0,
        key="wordcloud_category"
    )
    
    counter = active_categories[selected_category]
    
    # Statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Items", f"{len(counter):,}")
    with col2:
        st.metric("Total Mentions", f"{sum(counter.values()):,}")
    with col3:
        most_common = counter.most_common(1)[0] if counter else ("N/A", 0)
        st.metric("Most Common", most_common[0][:20] + ("..." if len(most_common[0]) > 20 else ""))
    with col4:
        st.metric("Mentions", f"{most_common[1]:,}")
    
    st.markdown("---")
    
    # Generate word cloud
    if counter:
        st.subheader(f"☁️ {selected_category} Word Cloud")
        
        # Create text for word cloud (repeat words by frequency, with max limit)
        word_freq = {}
        max_freq = max(counter.values()) if counter.values() else 1
        
        for word, count in counter.items():
            # Normalize frequency (scale to reasonable range for word cloud)
            # Most common gets max weight, others scaled proportionally
            normalized_count = min(count * 10, 100)  # Cap at 100 to prevent huge words
            word_freq[word] = normalized_count
        
        # Generate word cloud
        try:
            wordcloud = WordCloud(
                width=1200,
                height=600,
                background_color='white',
                colormap='Reds',
                max_words=100,
                relative_scaling=0.5,
                collocations=False,
                min_font_size=10,
                max_font_size=120,
                prefer_horizontal=0.7
            ).generate_from_frequencies(word_freq)
            
            # Display word cloud
            fig, ax = plt.subplots(figsize=(16, 8))
            ax.imshow(wordcloud, interpolation='bilinear')
            ax.axis('off')
            plt.tight_layout(pad=0)
            st.pyplot(fig)
            plt.close(fig)
            
            # Show top items as a table
            st.markdown("---")
            st.subheader("📊 Top Items (Ranked)")
            
            top_items = counter.most_common(50)
            df_top = pd.DataFrame(top_items, columns=['Item', 'Mentions'])
            df_top['Rank'] = range(1, len(df_top) + 1)
            df_top = df_top[['Rank', 'Item', 'Mentions']]
            
            # Display as table
            try:
                st.dataframe(df_top, use_container_width=True, hide_index=True)
            except:
                st.write(df_top.to_html(escape=False, index=False), unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"Error generating word cloud: {e}")
            st.info("Showing top items as a list instead:")
            top_items = counter.most_common(30)
            for i, (item, count) in enumerate(top_items, 1):
                st.write(f"{i}. **{item}** ({count:,} mentions)")
    else:
        st.info(f"No data available for {selected_category}")
    
    # Show all categories in tabs
    st.markdown("---")
    st.subheader("📋 All Categories Overview")
    
    # Create tabs for different category groups
    tab1, tab2, tab3 = st.tabs(["💊 Drugs & Interventions", "🧬 Biomolecules", "⚠️ Risk & Outcomes"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            if '💊 Drugs' in active_categories:
                st.markdown("#### 💊 Top Drugs")
                top_drugs = category_data['💊 Drugs'].most_common(20)
                df_drugs = pd.DataFrame(top_drugs, columns=['Drug', 'Mentions'])
                st.dataframe(df_drugs, use_container_width=True, hide_index=True)
        
        with col2:
            if '💉 Therapeutic Interventions' in active_categories:
                st.markdown("#### 💉 Top Interventions")
                top_int = category_data['💉 Therapeutic Interventions'].most_common(20)
                df_int = pd.DataFrame(top_int, columns=['Intervention', 'Mentions'])
                st.dataframe(df_int, use_container_width=True, hide_index=True)
    
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            if '🧬 Lipoproteins' in active_categories:
                st.markdown("#### 🧬 Top Lipoproteins")
                top_lp = category_data['🧬 Lipoproteins'].most_common(20)
                df_lp = pd.DataFrame(top_lp, columns=['Lipoprotein', 'Mentions'])
                st.dataframe(df_lp, use_container_width=True, hide_index=True)
            
            if '🔬 Biomarkers' in active_categories:
                st.markdown("#### 🔬 Top Biomarkers")
                top_bio = category_data['🔬 Biomarkers'].most_common(20)
                df_bio = pd.DataFrame(top_bio, columns=['Biomarker', 'Mentions'])
                st.dataframe(df_bio, use_container_width=True, hide_index=True)
        
        with col2:
            if '🧪 Genes' in active_categories:
                st.markdown("#### 🧪 Top Genes")
                top_genes = category_data['🧪 Genes'].most_common(20)
                df_genes = pd.DataFrame(top_genes, columns=['Gene', 'Mentions'])
                st.dataframe(df_genes, use_container_width=True, hide_index=True)
            
            if '⚛️ Proteins' in active_categories:
                st.markdown("#### ⚛️ Top Proteins")
                top_prot = category_data['⚛️ Proteins'].most_common(20)
                df_prot = pd.DataFrame(top_prot, columns=['Protein', 'Mentions'])
                st.dataframe(df_prot, use_container_width=True, hide_index=True)
    
    with tab3:
        col1, col2 = st.columns(2)
        
        with col1:
            if '⚠️ Risk Factors' in active_categories:
                st.markdown("#### ⚠️ Top Risk Factors")
                top_risks = category_data['⚠️ Risk Factors'].most_common(20)
                df_risks = pd.DataFrame(top_risks, columns=['Risk Factor', 'Mentions'])
                st.dataframe(df_risks, use_container_width=True, hide_index=True)
            
            if '🏥 Comorbidities' in active_categories:
                st.markdown("#### 🏥 Top Comorbidities")
                top_com = category_data['🏥 Comorbidities'].most_common(20)
                df_com = pd.DataFrame(top_com, columns=['Comorbidity', 'Mentions'])
                st.dataframe(df_com, use_container_width=True, hide_index=True)
        
        with col2:
            if '🔬 Pathophysiology' in active_categories:
                st.markdown("#### 🔬 Top Pathophysiology Terms")
                top_patho = category_data['🔬 Pathophysiology'].most_common(20)
                df_patho = pd.DataFrame(top_patho, columns=['Term', 'Mentions'])
                st.dataframe(df_patho, use_container_width=True, hide_index=True)
            
            if '📈 Clinical Outcomes' in active_categories:
                st.markdown("#### 📈 Top Clinical Outcomes")
                top_outcomes = category_data['📈 Clinical Outcomes'].most_common(20)
                df_outcomes = pd.DataFrame(top_outcomes, columns=['Outcome', 'Mentions'])
                st.dataframe(df_outcomes, use_container_width=True, hide_index=True)


def render_data_table_page(all_data):
    """Render data table page with filtered and sorted publications"""
    st.header("📋 Data Table")
    
    st.markdown("""
    **Filtered publications table**  
    *Excludes review articles and systematic reviews. Sorted by data completeness (fewer missing values first).*
    """)
    
    # Note: Data is already filtered (reviews excluded in the source file)
    # But we'll still filter here as a safety measure
    excluded_types = ['review_article', 'systematic_review', 'Review Article', 'Systematic Review']
    
    filtered_data = []
    for pub in all_data:
        study_type = pub.get('study_type', '')
        if study_type and study_type not in excluded_types:
            filtered_data.append(pub)
    
    # Since the source file already excludes reviews, this should match all_data
    if len(filtered_data) == len(all_data):
        st.info(f"Showing {len(filtered_data):,} publications (original research only - reviews already excluded from source file)")
    else:
        st.info(f"Showing {len(filtered_data):,} publications (excluded {len(all_data) - len(filtered_data):,} review articles and systematic reviews)")
    
    if not filtered_data:
        st.warning("No publications found after filtering.")
        return
    
    # Calculate completeness score for each publication
    def calculate_completeness(pub):
        """Calculate completeness score - higher = more complete"""
        fields_to_check = [
            'extracted_lipoproteins',
            'extracted_biomarkers',
            'extracted_genes',
            'extracted_drugs',
            'extracted_risk_factors',
            'extracted_comorbidities'
        ]
        
        score = 0
        for field in fields_to_check:
            value = pub.get(field, [])
            if value and len(value) > 0:
                score += 1
        
        return score
    
    # Add completeness score and sort
    for pub in filtered_data:
        pub['_completeness'] = calculate_completeness(pub)
    
    # Sort by completeness (descending) and then by year (descending)
    filtered_data.sort(key=lambda x: (-x.get('_completeness', 0), -int(x.get('year', 0)) if x.get('year') else 0))
    
    # Prepare data for table
    table_data = []
    for pub in filtered_data:
        # Format lipoproteins
        lipoproteins = pub.get('extracted_lipoproteins', [])
        lipoproteins_str = ', '.join(lipoproteins) if isinstance(lipoproteins, list) and lipoproteins else (lipoproteins if lipoproteins else '')
        
        # Format biomarkers
        biomarkers = pub.get('extracted_biomarkers', [])
        biomarkers_str = ', '.join(biomarkers) if isinstance(biomarkers, list) and biomarkers else (biomarkers if biomarkers else '')
        
        # Format genes
        genes = pub.get('extracted_genes', [])
        genes_str = ', '.join(genes) if isinstance(genes, list) and genes else (genes if genes else '')
        
        # Format drugs
        drugs = pub.get('extracted_drugs', [])
        if isinstance(drugs, list):
            drug_names = []
            for drug in drugs:
                if isinstance(drug, dict):
                    drug_names.append(drug.get('name', str(drug)))
                else:
                    drug_names.append(str(drug))
            drugs_str = ', '.join(drug_names) if drug_names else ''
        else:
            drugs_str = str(drugs) if drugs else ''
        
        # Format risk factors
        risk_factors = pub.get('extracted_risk_factors', [])
        risk_factors_str = ', '.join(risk_factors) if isinstance(risk_factors, list) and risk_factors else (risk_factors if risk_factors else '')
        
        # Format comorbidities
        comorbidities = pub.get('extracted_comorbidities', [])
        comorbidities_str = ', '.join(comorbidities) if isinstance(comorbidities, list) and comorbidities else (comorbidities if comorbidities else '')
        
        # Get year
        year = pub.get('year', '')
        if year and year != 2026:  # Exclude 2026
            year_str = str(year)
        else:
            year_str = ''
        
        table_data.append({
            'PMID': pub.get('pmid', ''),
            'Study Type': pub.get('study_type', ''),
            'Lipoproteins': lipoproteins_str[:200] + '...' if len(lipoproteins_str) > 200 else lipoproteins_str,
            'Biomarkers': biomarkers_str[:200] + '...' if len(biomarkers_str) > 200 else biomarkers_str,
            'Genes': genes_str[:200] + '...' if len(genes_str) > 200 else genes_str,
            'Drugs': drugs_str[:200] + '...' if len(drugs_str) > 200 else drugs_str,
            'Risk Factors': risk_factors_str[:200] + '...' if len(risk_factors_str) > 200 else risk_factors_str,
            'Comorbidities': comorbidities_str[:200] + '...' if len(comorbidities_str) > 200 else comorbidities_str,
            'Year': year_str,
            '_completeness': pub.get('_completeness', 0)  # For sorting, will be removed
        })
    
    # Create DataFrame
    df = pd.DataFrame(table_data)
    
    # Remove completeness column from display and reorder columns to ensure Year is last
    df_display = df.drop(columns=['_completeness'])
    column_order = ['PMID', 'Study Type', 'Lipoproteins', 'Biomarkers', 'Genes', 'Drugs', 'Risk Factors', 'Comorbidities', 'Year']
    df_display = df_display[column_order]
    
    # Add year filter
    st.markdown("### 🔍 Filters")
    col1, col2 = st.columns(2)
    
    with col1:
        years = sorted(set(int(pub.get('year', 0)) for pub in filtered_data if pub.get('year') and pub.get('year') != 2026), reverse=True)
        if years:
            min_year = min(years)
            max_year = max(years)
            year_range = st.slider(
                "Year Range",
                min_value=min_year,
                max_value=max_year,
                value=(min_year, max_year),
                step=1,
                key="table_year_range"
            )
        else:
            year_range = None
    
    with col2:
        study_types = sorted(set(pub.get('study_type', '') for pub in filtered_data if pub.get('study_type')))
        selected_study_types = st.multiselect(
            "Study Types",
            options=study_types,
            default=study_types,
            key="table_study_types"
        )
    
    # Apply filters
    if year_range:
        df_filtered = df_display[
            (df_display['Year'].astype(str).str.isdigit()) &
            (df_display['Year'].astype(int) >= year_range[0]) &
            (df_display['Year'].astype(int) <= year_range[1])
        ]
    else:
        df_filtered = df_display.copy()
    
    if selected_study_types:
        df_filtered = df_filtered[df_filtered['Study Type'].isin(selected_study_types)]
    
    # Display table
    st.markdown(f"### 📊 Publications Table ({len(df_filtered):,} rows)")
    
    # Show completeness info
    st.caption(f"Publications sorted by data completeness (most complete first). Showing top {len(df_filtered):,} publications.")
    
    # Display table
    try:
        st.dataframe(
            df_filtered,
            width='stretch',
            hide_index=True,
            height=600
        )
    except:
        # Fallback to HTML table
        st.write(df_filtered.to_html(escape=False, index=False), unsafe_allow_html=True)
    
    # Download button
    st.markdown("---")
    csv = df_filtered.to_csv(index=False)
    st.download_button(
        label="📥 Download Filtered Table as CSV",
        data=csv,
        file_name=f"athero_table_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )


def render_settings_page(all_data, categories):
    """Render settings and export page"""
    st.header("⚙️ Settings & Export")
    
    # Database statistics
    st.subheader("📊 Database Statistics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Publications", f"{len(all_data):,}")
    with col2:
        years = set(pub.get('year') for pub in all_data if pub.get('year'))
        st.metric("Year Range", f"{min(years, default='N/A')} - {max(years, default='N/A')}")
    with col3:
        st.metric("Categories", len(categories))
    
    st.markdown("---")
    
    # Export options
    st.subheader("💾 Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 Export All to JSON"):
            filename = f"athero_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)
            st.success(f"Exported to {filename}")
    
    with col2:
        if st.button("📥 Export All to CSV"):
            # Convert to DataFrame
            df_data = []
            for pub in all_data:
                abstract = pub.get('abstract') or ''
                df_data.append({
                    'PMID': pub.get('pmid') or '',
                    'Title': pub.get('title') or '',
                    'Year': pub.get('year') or '',
                    'Journal': pub.get('journal') or '',
                    'Abstract': abstract[:500] if abstract else ''
                })
            df = pd.DataFrame(df_data)
            filename = f"athero_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(filename, index=False)
            st.success(f"Exported to {filename}")


def main():
    """Main application entry point"""
    
    # Load data
    if not st.session_state.data_loaded:
        with st.spinner("Loading atherosclerosis data..."):
            all_data, yearly_counts, categories = load_all_data()
            st.session_state.all_data = all_data
            st.session_state.yearly_counts = yearly_counts
            st.session_state.categories = categories
            st.session_state.data_loaded = True
    
    all_data = st.session_state.all_data
    yearly_counts = st.session_state.yearly_counts
    categories = st.session_state.categories
    
    # Render sidebar and get selections
    page, year_range, category, cancer_type = render_sidebar()
    
    # Filter data based on selections (filters are disabled, so use all data)
    filtered_data = all_data
    
    # Render selected page
    if "Overview" in page:
        render_overview_page(filtered_data, yearly_counts, categories)
    elif "Search" in page:
        render_search_page(filtered_data)
    elif "Advanced Filters" in page:
        render_advanced_filters_page(all_data)
    elif "Filter & Visualize" in page:
        render_filter_visualize_page(all_data)
    elif "Trend by Entity" in page:
        render_trend_by_entity_page(all_data)
    elif "Field Analysis & Correlations" in page:
        render_field_analysis_page(all_data)
    elif "Word Clouds" in page:
        render_wordclouds_page(all_data)
    elif "Data Table" in page:
        render_data_table_page(all_data)
    elif "AI Q&A" in page:
        if AGENTS_AVAILABLE:
            render_qa_page(all_data)
        else:
            st.warning("⚠️ AI Agents not available")
            if AGENTS_ERROR:
                st.error(f"**Error:** {AGENTS_ERROR}")
            st.info("""
            **To enable AI Agents:**
            
            1. **Install dependencies:**
               ```bash
               pip install openai anthropic
               ```
            
            2. **Ensure directory structure:**
               - The `athero/agents/` directory must exist
               - It should contain `qa_agent.py`, `publication_analyzer.py`, `synthesis_agent.py`
               - The `athero/render_agents.py` file must exist
            
            3. **Configure API keys in `.env` file:**
               - `OPENAI_API_KEY=your_key`
               - `ANTHROPIC_API_KEY=your_key`
            """)
    elif "Publication Analysis" in page:
        if AGENTS_AVAILABLE:
            render_publication_analysis_page(all_data)
        else:
            st.warning("⚠️ AI Agents not available")
            if AGENTS_ERROR:
                st.error(f"**Error:** {AGENTS_ERROR}")
            st.info("""
            **To enable AI Agents:**
            
            1. **Install dependencies:**
               ```bash
               pip install openai anthropic chromadb
               ```
            
            2. **Ensure directory structure:**
               - The `mirna_analysis` directory must exist in the project root
               - It should contain `agents/` and `render_agents.py`
            
            3. **Configure API keys in `.env` file**
            """)
    elif "Research Synthesis" in page:
        if AGENTS_AVAILABLE:
            render_synthesis_page(all_data)
        else:
            st.warning("⚠️ AI Agents not available")
            if AGENTS_ERROR:
                st.error(f"**Error:** {AGENTS_ERROR}")
            st.info("""
            **To enable AI Agents:**
            
            1. **Install dependencies:**
               ```bash
               pip install openai anthropic chromadb
               ```
            
            2. **Ensure directory structure:**
               - The `mirna_analysis` directory must exist in the project root
               - It should contain `agents/` and `render_agents.py`
            
            3. **Configure API keys in `.env` file**
            """)
    elif "Literature Review" in page:
        if AGENTS_AVAILABLE:
            render_literature_review_page(all_data)
        else:
            st.warning("⚠️ AI Agents not available")
            if AGENTS_ERROR:
                st.error(f"**Error:** {AGENTS_ERROR}")
            st.info("""
            **To enable AI Agents:**
            
            1. **Install dependencies:**
               ```bash
               pip install openai anthropic python-dotenv
               ```
            
            2. **Configure API keys in `.env` file:**
               - `OPENAI_API_KEY=your_key`
               - `ANTHROPIC_API_KEY=your_key`
            """)
    elif "Publications" in page:
        render_publications_page(filtered_data)
    elif "Settings" in page:
        render_settings_page(all_data, categories)


if __name__ == "__main__":
    main()

