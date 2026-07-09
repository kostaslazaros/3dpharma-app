# AgentAthero: Atherosclerosis & Lipoproteins Research System

**AI-Powered Knowledge Extraction System**  
*Mapping thousands of studies and building an interactive system with artificial intelligence agents*

Based on the research described in:
> "ATHEROSCLEROSIS AND LIPOPROTEINS: MAPPING THOUSANDS OF STUDIES AND BUILDING AN INTERACTIVE SYSTEM WITH ARTIFICIAL INTELLIGENCE AGENTS"

## Overview

AgentAthero is an AI-powered system for automated extraction, analysis, and visualization of atherosclerosis and lipoprotein research from PubMed. The system uses:

- **Hybrid NLP/LLM Extraction**: Combines regex pre-extraction with GPT-4o for comprehensive field extraction
- **Structured Data Extraction**: Extracts 12+ fields including lipoproteins, biomarkers, genes, proteins, therapeutic interventions, risk factors, pathophysiology, clinical outcomes, and more
- **Interactive Visualization**: Streamlit-based web interface for exploring thousands of publications
- **AI-Powered Q&A**: LLM-based system to answer clinical questions using knowledge from extracted studies

## Features

### Extraction Fields

1. **Lipoproteins & Apolipoproteins**: LDL, HDL, VLDL, ApoA1, ApoB, ApoE, etc.
2. **Biomarkers**: CRP, hs-CRP, troponin, BNP, TMAO, homocysteine, etc.
3. **Genes**: Lipid metabolism genes, inflammatory genes, endothelial function genes, etc.
4. **Proteins**: Apolipoproteins, enzymes, receptors, adhesion molecules, etc.
5. **Therapeutic Interventions**: Statins, PCSK9 inhibitors, antiplatelet agents, etc.
6. **Risk Factors**: Traditional and non-traditional cardiovascular risk factors
7. **Pathophysiology**: Mechanisms of atherosclerosis development and progression
8. **Clinical Outcomes**: MACE, MI, stroke, cardiovascular death, etc.
9. **Thematic Categories**: Study classification (clinical trials, observational studies, etc.)
10. **Correlations**: Relationships between variables and outcomes
11. **Study Type**: Classification of study design
12. **Patient Count**: Sample sizes

## Quick Start

### 1. Extract Data from PubMed

```bash
# From the project root directory
python extract_athero.py
```

This will:
- Search PubMed for atherosclerosis and lipoprotein publications (2020-2025)
- Extract structured data using AI/NLP
- Save results to `athero.json`

**Note**: Requires `OPENAI_API_KEY` in your `.env` file or environment variables.

### 2. Launch Visualization App

```bash
# From the project root directory
streamlit run athero/app.py
```

The app will open in your browser at `http://localhost:8501`

## App Features

### 📊 Overview Page
- Key metrics and statistics
- Publication trends over time
- Top lipoproteins and biomarkers
- Structured data table with filters

### 🔍 Search Page
- Full-text search across titles and abstracts
- Direct links to PubMed

### 🎯 Advanced Filters
- Filter by lipoproteins, biomarkers, interventions, risk factors
- Year range selection
- Multiple filter combinations

### 📉 Filter & Visualize
- Dynamic visualizations based on filters
- Publication timelines
- Top entities charts
- Cumulative publication trends

### 📅 Trend by Entity
- Analyze publication trends for specific lipoproteins, biomarkers, or interventions
- Comparative trend lines
- Stacked area charts

### 🤖 AI Q&A (if agents available)
- Ask clinical questions
- Get answers based on extracted knowledge
- Documented responses with references

### 🛡️ Trust Metrics (optional)
- Enable the “Compute trust metrics” toggle on the Q&A page to score every answer
- Metrics include semantic similarity, grounding score, NLI-based faithfulness, cross-encoder relevance, and context precision
- Helps flag topic drift, unsupported claims, hallucinations, and noisy retrieval
- Requires optional dependencies: `pip install sentence-transformers transformers`

### 📖 Publications
- Browse all publications
- Paginated view
- Direct PubMed links

## Data Structure

The extracted data is saved in `athero.json` with the following structure:

```json
{
  "metadata": {
    "domain": "atherosclerosis_lipoproteins",
    "extraction_date": "2025-01-XX...",
    "total_publications": 1234,
    "date_range": "2020-2025"
  },
  "publications": [
    {
      "id": 1,
      "pmid": "12345678",
      "title": "...",
      "abstract": "...",
      "publication_date": "2024-01-15T00:00:00",
      "extracted_lipoproteins": ["LDL", "HDL", "ApoB"],
      "extracted_biomarkers": ["CRP", "hs-CRP", "TMAO"],
      "extracted_genes": ["APOB", "APOE", "LDLR"],
      "extracted_proteins": ["ApoB", "ApoE", "LDL receptor"],
      "extracted_therapeutic_interventions": ["atorvastatin", "aspirin"],
      "extracted_risk_factors": ["hypertension", "diabetes"],
      "extracted_pathophysiology": ["LDL oxidation", "foam cell formation"],
      "extracted_clinical_outcomes": ["MACE", "MI"],
      "extracted_thematic_categories": ["clinical_trial", "biomarker_study"],
      "extracted_correlations": ["high CRP associated with increased cardiovascular risk"],
      "study_type": "randomized_controlled_trial",
      "patient_count": 1000
    }
  ]
}
```

## PubMed Query

The system searches PubMed using MeSH terms and keywords:

```
(atherosclerosis[MeSH Terms] OR atherosclerosis[Title/Abstract] OR
lipoproteins[MeSH Terms] OR lipoproteins[Title/Abstract] OR
LDL[Title/Abstract] OR HDL[Title/Abstract] OR
apolipoprotein[Title/Abstract] OR cholesterol[MeSH Terms] OR
cardiovascular disease[MeSH Terms] OR coronary artery disease[MeSH Terms] OR
carotid atherosclerosis[Title/Abstract] OR plaque[Title/Abstract])
```

Date range: 2020-2025 (as described in the abstract)

## Requirements

- Python 3.8+
- OpenAI API key (for GPT-4o extraction)
- Required packages (see `requirements.txt`):
  - streamlit
  - pandas
  - plotly
  - openai
  - biopython (for PubMed API)
  - python-dotenv

## Methodology

The extraction uses a **hybrid approach**:

1. **Regex Pre-extraction**: Fast pattern matching for common lipoproteins and biomarkers
2. **LLM Extraction**: GPT-4o with structured prompts for comprehensive field extraction
3. **Merging & Deduplication**: Combines regex and LLM results

This approach balances speed and accuracy, ensuring comprehensive extraction while maintaining performance.

## Citation

If you use this system, please cite:

> "ATHEROSCLEROSIS AND LIPOPROTEINS: MAPPING THOUSANDS OF STUDIES AND BUILDING AN INTERACTIVE SYSTEM WITH ARTIFICIAL INTELLIGENCE AGENTS"

## Support

For issues or questions, please check:
- Main project README: `../README.md`
- Troubleshooting guide: `../TROUBLESHOOTING.md`

## License

See main project license.

