import { useState, useMemo } from "react";
import * as Recharts from "recharts";

// ═══════════════════════════════════════════════════════════════════════════════
//  DATA (precomputed from athero_nlp_with_relationships.json — 7,905 papers)
// ═══════════════════════════════════════════════════════════════════════════════

const DATA = {
  total_papers: 7905,
  yearly_counts: {"2020":896,"2021":1348,"2022":1625,"2023":1745,"2024":1792} as Record<string,number>,

  entity_stats: {
    lipoprotein: { unique:26, total_mentions:19214, pubs_with_data:5765, coverage_pct:72.9, top_20:[["LDL",5807],["HDL",3459],["Triglycerides",2165],["LDL-C",1544],["Lp(a)",1181],["ApoB",962],["Total Cholesterol",811],["HDL-C",758],["ApoE",638],["Non-HDL",375],["VLDL",337],["oxLDL",285],["ApoA",216],["ox-LDL",150],["IDL",82],["non-HDL cholesterol",73],["LDL-c",55],["HDL-c",48],["apolipoprotein B",44],["Lipoprotein(a)",39]] },
    biomarker: { unique:194, total_mentions:3269, pubs_with_data:1910, coverage_pct:24.2, top_20:[["CRP",620],["hs-CRP",337],["IL-6",231],["TNF-α",186],["VCAM-1",130],["ICAM-1",120],["IL-1β",109],["fibrinogen",97],["TMAO",96],["homocysteine",91],["IL-10",72],["MCP-1",67],["IL-1",65],["MPO",54],["MMP-9",51],["galectin-3",46],["IL-18",40],["Lp-PLA2",38],["GDF-15",35],["PCSK9",34]] },
    gene: { unique:444, total_mentions:6392, pubs_with_data:2838, coverage_pct:35.9, top_20:[["PCSK9",652],["APOE",386],["ACE",208],["ABCA1",203],["LDLR",200],["CETP",164],["NPC1L1",139],["HMGCR",132],["PON1",115],["MTHFR",104],["APOB",100],["LOX-1",97],["SR-BI",91],["TNF",88],["eNOS",87],["ABCG1",85],["SORT1",82],["LPA",77],["ANGPTL3",74],["IL6",71]] },
    protein: { unique:2972, total_mentions:17519, pubs_with_data:5296, coverage_pct:67.0, top_20:[["LDL-C",1544],["follow-up",902],["HDL-C",758],["PCSK9",476],["high-fat",275],["NF-κB",237],["THP-1",231],["ApoE",211],["collagen",195],["MMP",174],["AMPK",170],["Nrf2",161],["p53",155],["NLRP3",153],["PI3K",150],["ABCA1",147],["eNOS",140],["HMGCR",137],["SREBP",135],["mTOR",131]] },
    drug: { unique:174, total_mentions:2260, pubs_with_data:1403, coverage_pct:17.7, top_20:[["ezetimibe",331],["atorvastatin",169],["aspirin",134],["evolocumab",124],["rosuvastatin",101],["alirocumab",84],["simvastatin",80],["rivaroxaban",78],["clopidogrel",74],["inclisiran",74],["bempedoic acid",61],["ticagrelor",43],["colchicine",43],["niacin",41],["pitavastatin",33],["plasminogen",33],["warfarin",31],["pravastatin",30],["omega-3 fatty acids",26],["icosapent",24]] },
    risk_factor: { unique:137, total_mentions:8497, pubs_with_data:5103, coverage_pct:64.5, top_20:[["hypertension",1361],["diabetes",1332],["smoking",1294],["obesity",1050],["dyslipidemia",661],["hyperlipidemia",414],["insulin resistance",297],["metabolic syndrome",279],["hyperglycemia",215],["chronic kidney disease",180],["type 2 diabetes",167],["inflammation",162],["hypercholesterolemia",157],["oxidative stress",142],["endothelial dysfunction",135],["aging",99],["sedentary lifestyle",86],["family history",85],["hypertriglyceridemia",74],["air pollution",72]] },
    comorbidity: { unique:90, total_mentions:9096, pubs_with_data:5289, coverage_pct:66.9, top_20:[["coronary artery disease",2689],["stroke",1032],["heart failure",937],["myocardial infarction",811],["CAD",780],["peripheral artery disease",527],["atrial fibrillation",379],["chronic kidney disease",346],["type 2 diabetes",332],["aortic stenosis",301],["coronary heart disease",283],["CHD",274],["hypertension",246],["PAD",186],["diabetes mellitus",173],["NAFLD",152],["MI",115],["deep vein thrombosis",84],["T2DM",79],["pulmonary embolism",78]] },
    pathophysiology: { unique:117, total_mentions:3152, pubs_with_data:2218, coverage_pct:28.1, top_20:[["endothelial dysfunction",420],["oxidative stress",391],["inflammation",389],["plaque formation",186],["foam cell formation",172],["vascular calcification",167],["thrombosis",158],["lipid accumulation",139],["plaque rupture",128],["neointimal hyperplasia",105],["vascular remodeling",100],["macrophage polarization",95],["cholesterol efflux",92],["autophagy",80],["apoptosis",78],["angiogenesis",73],["arterial stiffness",63],["vascular smooth muscle cell proliferation",56],["reverse cholesterol transport",49],["platelet aggregation",48]] },
    clinical_outcome: { unique:89, total_mentions:7651, pubs_with_data:4563, coverage_pct:57.7, top_20:[["cardiovascular events",1147],["mortality",870],["MACE",739],["plaque regression",416],["LDL-C reduction",399],["cardiovascular mortality",394],["all-cause mortality",337],["stent thrombosis",261],["restenosis",239],["bleeding",237],["myocardial infarction",222],["stroke",220],["hospitalization",198],["revascularization",193],["plaque progression",178],["target lesion revascularization",172],["cardiovascular death",171],["coronary events",167],["heart failure hospitalization",152],["recurrent events",118]] },
    therapeutic_intervention: { unique:136, total_mentions:7571, pubs_with_data:4763, coverage_pct:60.3, top_20:[["statin therapy",1544],["PCI",760],["CABG",476],["lipid-lowering therapy",455],["antiplatelet therapy",407],["PCSK9 inhibitors",378],["dual antiplatelet therapy",295],["ezetimibe",275],["lifestyle modification",244],["coronary artery bypass grafting",231],["exercise",206],["diet",193],["immunotherapy",174],["anti-inflammatory therapy",170],["gene therapy",161],["nanoparticle therapy",150],["stem cell therapy",140],["percutaneous coronary intervention",137],["omega-3 supplementation",131],["antioxidant therapy",119]] },
    thematic_category: { unique:33, total_mentions:20447, pubs_with_data:7734, coverage_pct:97.8, top_20:[["Lipid Metabolism",3255],["Treatment Outcomes",2649],["Inflammation & Immune Response",2337],["Cardiovascular Risk",2042],["Plaque Biology",1771],["Clinical Trials",1407],["Interventional Cardiology",1280],["Genetics & Genomics",1008],["Diagnostic Biomarkers",953],["Drug Therapy",903],["Metabolic Syndrome",720],["Vascular Biology",694],["Epidemiology",540],["Imaging & Diagnostics",418],["Comorbidities",376],["Public Health",239],["Peripheral Vascular",209],["Pediatric",93],["Novel Therapeutics",83],["Nanotechnology",78]] },
  } as Record<string, {unique:number, total_mentions:number, pubs_with_data:number, coverage_pct:number, top_20:[string,number][]}>,

  drug_categories: {"Lipid-lowering":1418,"Antiplatelet":305,"Anticoagulant":252,"Anti-inflammatory":153,"Novel therapies":59,"Antihypertensive":49,"Unknown":24} as Record<string,number>,

  relationships: {
    total:84769, papers_with:5598,
    types:{"associated_with":26984,"modulates":14847,"risk_factor_for":12424,"involved_in":9614,"reduces":6448,"marker_for":4543,"increases":3458,"treats":2516,"mechanism_of":1647,"targets":1203,"prevents":473,"inhibits":338,"promotes":180,"regulates":94} as Record<string,number>,
    top_pairs:{"lipoprotein → comorbidity":22924,"risk_factor → comorbidity":16876,"gene → lipoprotein":9321,"biomarker → comorbidity":6847,"drug → lipoprotein":5414,"gene → comorbidity":4988,"drug → comorbidity":2253,"biomarker → lipoprotein":2216,"risk_factor → lipoprotein":1936,"pathophysiology → comorbidity":1724} as Record<string,number>,
  },

  correlations: {
    total:433, unique:312,
    top_30:[["Higher LDL-C levels are associated with increased cardiovascular risk",8],["Statin therapy reduces LDL-C and cardiovascular events",7],["Elevated Lp(a) is an independent risk factor for cardiovascular disease",6],["PCSK9 inhibitors significantly reduce LDL-C levels",5],["HDL cholesterol is inversely associated with cardiovascular risk",5],["Inflammation plays a key role in atherosclerosis progression",4],["Oxidative stress contributes to endothelial dysfunction",4],["Triglycerides are associated with residual cardiovascular risk",4],["Smoking is a major modifiable risk factor for atherosclerosis",3],["Diabetes accelerates atherosclerosis progression",3]] as [string,number][],
  },

  er_groups: [
    {type:"lipoprotein",canonical_id:"CHEBI:47774",canonical_name:"LDL",variants:[{name:"LDL",count:5807},{name:"low-density lipoprotein",count:19},{name:"Low-density lipoprotein",count:3},{name:"low density lipoprotein",count:1}],total_mentions:5830},
    {type:"comorbidity",canonical_id:"MESH:D003324",canonical_name:"coronary artery disease",variants:[{name:"coronary artery disease",count:2689},{name:"CAD",count:780},{name:"coronary heart disease",count:283},{name:"CHD",count:274}],total_mentions:4026},
    {type:"lipoprotein",canonical_id:"CHEBI:39025",canonical_name:"HDL",variants:[{name:"HDL",count:3459},{name:"high-density lipoprotein",count:14}],total_mentions:3473},
    {type:"lipoprotein",canonical_id:"CHEBI:17855_TG",canonical_name:"triglycerides",variants:[{name:"Triglycerides",count:1311},{name:"triglycerides",count:774},{name:"TG",count:67},{name:"triglyceride",count:8},{name:"Triglyceride",count:5}],total_mentions:2165},
    {type:"lipoprotein",canonical_id:"CHEBI:47774_C",canonical_name:"LDL cholesterol",variants:[{name:"LDL-C",count:1544},{name:"low-density lipoprotein cholesterol",count:12},{name:"LDLC",count:8},{name:"LDLCHOLESTEROL",count:2}],total_mentions:1566},
    {type:"risk_factor",canonical_id:"MESH:D003920",canonical_name:"diabetes",variants:[{name:"diabetes",count:1332},{name:"diabetes mellitus",count:173}],total_mentions:1505},
    {type:"lipoprotein",canonical_id:"NCBI:gene/4018",canonical_name:"lipoprotein(a)",variants:[{name:"Lp(a)",count:1181},{name:"Lipoprotein(a)",count:39},{name:"lipoprotein(a)",count:28},{name:"Lipoprotein-a",count:3}],total_mentions:1251},
    {type:"lipoprotein",canonical_id:"UniProt:P04114",canonical_name:"apolipoprotein B",variants:[{name:"ApoB",count:962},{name:"apolipoprotein B",count:44},{name:"Apolipoprotein B",count:8},{name:"apoB",count:7},{name:"ApoB-100",count:5}],total_mentions:1026},
    {type:"biomarker",canonical_id:"UniProt:P02741",canonical_name:"C-reactive protein",variants:[{name:"CRP",count:620},{name:"hs-CRP",count:337},{name:"hsCRP",count:18},{name:"C-reactive protein",count:12}],total_mentions:987},
    {type:"comorbidity",canonical_id:"MESH:D009203",canonical_name:"myocardial infarction",variants:[{name:"myocardial infarction",count:811},{name:"MI",count:115}],total_mentions:926},
    {type:"lipoprotein",canonical_id:"CHEBI:17855",canonical_name:"total cholesterol",variants:[{name:"Total Cholesterol",count:755},{name:"total cholesterol",count:50},{name:"TC",count:6}],total_mentions:811},
    {type:"lipoprotein",canonical_id:"CHEBI:39025_C",canonical_name:"HDL cholesterol",variants:[{name:"HDL-C",count:758},{name:"HDL cholesterol",count:22},{name:"high-density lipoprotein cholesterol",count:9},{name:"HDLC",count:5}],total_mentions:794},
    {type:"comorbidity",canonical_id:"MESH:D058729",canonical_name:"peripheral artery disease",variants:[{name:"peripheral artery disease",count:527},{name:"PAD",count:186}],total_mentions:713},
    {type:"lipoprotein",canonical_id:"UniProt:P02649",canonical_name:"apolipoprotein E",variants:[{name:"ApoE",count:638},{name:"apolipoprotein E",count:5},{name:"apoE",count:3}],total_mentions:646},
    {type:"lipoprotein",canonical_id:"CHEBI:60151",canonical_name:"oxidized LDL",variants:[{name:"oxLDL",count:285},{name:"ox-LDL",count:150},{name:"oxidized LDL",count:37},{name:"oxidized low-density lipoprotein",count:10}],total_mentions:482},
    {type:"lipoprotein",canonical_id:"non-HDL",canonical_name:"non-HDL cholesterol",variants:[{name:"Non-HDL",count:375},{name:"non-HDL cholesterol",count:73},{name:"non-HDL-C",count:4}],total_mentions:452},
    {type:"comorbidity",canonical_id:"MESH:D003924",canonical_name:"type 2 diabetes",variants:[{name:"type 2 diabetes",count:332},{name:"T2DM",count:79},{name:"Type 2 diabetes",count:17}],total_mentions:428},
    {type:"comorbidity",canonical_id:"MESH:D051436",canonical_name:"chronic kidney disease",variants:[{name:"chronic kidney disease",count:346},{name:"CKD",count:5}],total_mentions:351},
    {type:"lipoprotein",canonical_id:"CHEBI:39027",canonical_name:"VLDL",variants:[{name:"VLDL",count:337}],total_mentions:337},
    {type:"biomarker",canonical_id:"NCBI:gene/3569",canonical_name:"IL-6",variants:[{name:"IL-6",count:231},{name:"interleukin-6",count:9}],total_mentions:240},
    {type:"lipoprotein",canonical_id:"UniProt:P02647",canonical_name:"apolipoprotein A-I",variants:[{name:"ApoA",count:216},{name:"ApoA1",count:10},{name:"apolipoprotein A1",count:3}],total_mentions:229},
    {type:"biomarker",canonical_id:"NCBI:gene/7124",canonical_name:"TNF-α",variants:[{name:"TNF-α",count:186},{name:"TNF-alpha",count:11}],total_mentions:197},
    {type:"risk_factor",canonical_id:"MESH:D003924",canonical_name:"type 2 diabetes",variants:[{name:"type 2 diabetes",count:167},{name:"T2DM",count:6}],total_mentions:173},
    {type:"comorbidity",canonical_id:"MESH:D003920",canonical_name:"diabetes mellitus",variants:[{name:"diabetes mellitus",count:173}],total_mentions:173},
    {type:"biomarker",canonical_id:"CHEBI:17588",canonical_name:"homocysteine",variants:[{name:"homocysteine",count:91},{name:"Hcy",count:5}],total_mentions:96},
    {type:"biomarker",canonical_id:"UniProt:P05164",canonical_name:"myeloperoxidase",variants:[{name:"myeloperoxidase",count:54},{name:"MPO",count:10}],total_mentions:64},
    {type:"pathophysiology",canonical_id:"GO:0043691",canonical_name:"reverse cholesterol transport",variants:[{name:"reverse cholesterol transport",count:49},{name:"RCT",count:3}],total_mentions:52},
    {type:"risk_factor",canonical_id:"MESH:D015992",canonical_name:"BMI",variants:[{name:"BMI",count:26},{name:"body mass index",count:20}],total_mentions:46},
    {type:"gene",canonical_id:"NCBI:gene/6347",canonical_name:"CCL2",variants:[{name:"CCL2",count:14},{name:"MCP1",count:2}],total_mentions:16},
    {type:"gene",canonical_id:"NCBI:gene/7412",canonical_name:"VCAM1",variants:[{name:"VCAM1",count:8}],total_mentions:8},
    {type:"gene",canonical_id:"NCBI:gene/3383",canonical_name:"ICAM1",variants:[{name:"ICAM1",count:5}],total_mentions:5},
  ] as {type:string,canonical_id:string,canonical_name:string,variants:{name:string,count:number}[],total_mentions:number}[],

  er_false_positives: [
    {term:"LDL-C",count:1544,should_be:"lipoprotein"},{term:"follow-up",count:902,should_be:"not an entity"},
    {term:"HDL-C",count:758,should_be:"lipoprotein"},{term:"high-fat",count:275,should_be:"not an entity"},
    {term:"THP-1",count:231,should_be:"not an entity"},{term:"ox-LDL",count:150,should_be:"lipoprotein"},
    {term:"non-HDL",count:66,should_be:"lipoprotein"},{term:"LDL-c",count:55,should_be:"lipoprotein"},
    {term:"HDL-c",count:48,should_be:"lipoprotein"},
  ] as {term:string,count:number,should_be:string}[],
  total_protein_mentions: 17519,

  er_conflicts: [
    {entity:"LDL-C",types:["lipoprotein","protein"],total_mentions:3088},
    {entity:"HDL-C",types:["lipoprotein","protein"],total_mentions:1516},
    {entity:"PCSK9",types:["gene","protein"],total_mentions:1128},
    {entity:"follow-up",types:["protein","risk_factor"],total_mentions:902},
    {entity:"ApoE",types:["lipoprotein","protein"],total_mentions:849},
    {entity:"ABCA1",types:["gene","protein"],total_mentions:350},
    {entity:"IL-6",types:["biomarker","gene"],total_mentions:302},
    {entity:"eNOS",types:["gene","protein"],total_mentions:227},
    {entity:"TNF",types:["biomarker","gene"],total_mentions:156},
    {entity:"LOX-1",types:["biomarker","gene"],total_mentions:130},
  ] as {entity:string,types:string[],total_mentions:number}[],

  entity_yearly_trends: {
    "lipoprotein:LDL":{"2020":820,"2021":1051,"2022":1239,"2023":1295,"2024":1254},
    "lipoprotein:HDL":{"2020":510,"2021":624,"2022":763,"2023":724,"2024":733},
    "lipoprotein:Triglycerides":{"2020":311,"2021":374,"2022":464,"2023":474,"2024":452},
    "lipoprotein:Lp(a)":{"2020":110,"2021":167,"2022":220,"2023":267,"2024":327},
    "gene:PCSK9":{"2020":87,"2021":107,"2022":136,"2023":140,"2024":148},
    "gene:APOE":{"2020":60,"2021":72,"2022":78,"2023":82,"2024":77},
    "biomarker:CRP":{"2020":98,"2021":114,"2022":122,"2023":130,"2024":126},
    "drug:ezetimibe":{"2020":38,"2021":52,"2022":60,"2023":78,"2024":80},
    "drug:evolocumab":{"2020":25,"2021":28,"2022":22,"2023":20,"2024":19},
    "drug:atorvastatin":{"2020":28,"2021":32,"2022":36,"2023":33,"2024":30},
  } as Record<string,Record<string,number>>,

  histograms: {
    lipoprotein:{mean:2.43,max:15,distribution:{"0":2140,"1":1230,"2":1180,"3":1040,"4":800,"5":560,"6":380,"7":230,"8":140,"9":80,"10":50}},
    biomarker:{mean:0.41,max:12,distribution:{"0":5995,"1":1010,"2":420,"3":210,"4":110,"5":60,"6":35,"7":20,"8":15}},
    gene:{mean:0.81,max:18,distribution:{"0":5067,"1":1320,"2":620,"3":380,"4":210,"5":120,"6":70,"7":40,"8":25}},
    drug:{mean:0.29,max:8,distribution:{"0":6502,"1":850,"2":310,"3":120,"4":60,"5":30,"6":15,"7":10,"8":8}},
    risk_factor:{mean:1.07,max:10,distribution:{"0":2802,"1":1950,"2":1380,"3":820,"4":450,"5":230,"6":120,"7":70,"8":40}},
    comorbidity:{mean:1.15,max:9,distribution:{"0":2616,"1":2020,"2":1450,"3":870,"4":470,"5":240,"6":120,"7":60,"8":35}},
  } as Record<string,{mean:number,max:number,distribution:Record<string,number>}>,
};

// ═══════════════════════════════════════════════════════════════════════════════
//  TYPES & CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════════
type Tab = "overview"|"trends"|"field_analysis"|"drugs"|"relationships"|"entities"|"ai_agent";

const P = { // purple clinical palette
  50:"#F5F0FF", 100:"#EDE5FF", 200:"#D4C4FB", 300:"#B89AF7", 400:"#9B6FE8",
  500:"#7C3AED", 600:"#6D28D9", 700:"#5B21B6", 800:"#4C1D95", 900:"#3B0764",
};
const TEAL = { 400:"#2DD4BF", 500:"#14B8A6", 600:"#0D9488" };
const ROSE = { 400:"#FB7185", 500:"#F43F5E" };
const AMBER = { 400:"#FBBF24", 500:"#F59E0B" };
const SKY = { 400:"#38BDF8", 500:"#0EA5E9" };
const EMERALD = { 400:"#34D399", 500:"#10B981" };

const TYPE_COLORS: Record<string,string> = {
  lipoprotein:"#7C3AED", comorbidity:"#F43F5E", biomarker:"#10B981",
  gene:"#0EA5E9", risk_factor:"#F59E0B", pathophysiology:"#A855F7",
  protein:"#14B8A6", drug:"#6D28D9", clinical_outcome:"#06B6D4",
  therapeutic_intervention:"#EF4444", thematic_category:"#6366F1",
};

const CHART_PALETTE = [P[500],TEAL[500],ROSE[500],AMBER[500],SKY[500],EMERALD[500],"#EC4899","#F97316","#6366F1","#84CC16"];

// ═══════════════════════════════════════════════════════════════════════════════
//  STYLES (clinical white/purple)
// ═══════════════════════════════════════════════════════════════════════════════
const css = {
  app: { display:"flex", minHeight:"100vh", background:"#F8F7FC", color:"#1E1B4B", fontFamily:"'Segoe UI','Helvetica Neue',Arial,sans-serif", fontSize:14 } as React.CSSProperties,
  sidebar: { width:250, minWidth:250, background:"#FFFFFF", borderRight:"1px solid #E8E4F0", padding:"24px 0", display:"flex", flexDirection:"column" as const, position:"sticky" as const, top:0, height:"100vh", overflowY:"auto" as const, boxShadow:"2px 0 8px rgba(124,58,237,0.04)" } as React.CSSProperties,
  sidebarTitle: { padding:"0 24px 20px", fontWeight:800, fontSize:17, color:P[700], letterSpacing:"-0.02em" } as React.CSSProperties,
  navItem: (active:boolean) => ({ padding:"11px 24px", fontSize:13.5, fontWeight:active?600:400, cursor:"pointer", background:active?P[50]:"transparent", color:active?P[700]:"#6B7280", borderLeft:active?`3px solid ${P[500]}`:"3px solid transparent", transition:"all 0.15s" } as React.CSSProperties),
  main: { flex:1, padding:"32px 40px", maxWidth:1400, overflowY:"auto" as const } as React.CSSProperties,
  h1: { fontSize:26, fontWeight:800, color:P[800], letterSpacing:"-0.03em", marginBottom:4 } as React.CSSProperties,
  h2: { fontSize:18, fontWeight:700, color:P[700], letterSpacing:"-0.02em", marginBottom:12, marginTop:28 } as React.CSSProperties,
  h3: { fontSize:14, fontWeight:600, color:"#4B5563", marginBottom:8 } as React.CSSProperties,
  sub: { fontSize:13.5, color:"#6B7280", marginBottom:24, lineHeight:1.6 } as React.CSSProperties,
  grid: (cols:number) => ({ display:"grid", gridTemplateColumns:`repeat(${cols}, 1fr)`, gap:14, marginBottom:20 } as React.CSSProperties),
  card: { background:"#FFFFFF", borderRadius:12, padding:"20px", border:"1px solid #E8E4F0", boxShadow:"0 1px 3px rgba(124,58,237,0.06)" } as React.CSSProperties,
  metricCard: (accent:string) => ({ background:"#FFFFFF", borderRadius:12, padding:"16px 18px", borderTop:`3px solid ${accent}`, border:"1px solid #E8E4F0", boxShadow:"0 1px 3px rgba(124,58,237,0.06)" } as React.CSSProperties),
  metricLabel: { fontSize:11, color:"#9CA3AF", textTransform:"uppercase" as const, letterSpacing:"0.06em", fontWeight:600, marginBottom:4 } as React.CSSProperties,
  metricVal: { fontSize:24, fontWeight:800, color:"#1E1B4B", letterSpacing:"-0.02em" } as React.CSSProperties,
  metricDelta: { fontSize:11, color:EMERALD[500], fontWeight:500, marginTop:2 } as React.CSSProperties,
  tabs: { display:"flex", gap:0, borderBottom:"2px solid #E8E4F0", marginBottom:24 } as React.CSSProperties,
  tabBtn: (a:boolean) => ({ padding:"10px 20px", fontSize:13, fontWeight:a?600:400, cursor:"pointer", color:a?P[700]:"#9CA3AF", borderBottom:a?`2px solid ${P[500]}`:"2px solid transparent", background:"transparent", border:"none", marginBottom:"-2px", transition:"all 0.15s" } as React.CSSProperties),
  tag: (c:string) => ({ display:"inline-block", padding:"2px 10px", borderRadius:20, fontSize:11, fontWeight:600, background:`${c}18`, color:c, marginRight:5, marginBottom:3 } as React.CSSProperties),
  pill: { display:"inline-flex", alignItems:"center", gap:4, padding:"3px 10px", borderRadius:20, fontSize:11, fontWeight:500, background:"#F3F0FF", color:P[600], border:`1px solid ${P[200]}` } as React.CSSProperties,
  select: { padding:"8px 14px", borderRadius:8, border:"1px solid #E8E4F0", background:"#FFFFFF", color:"#1E1B4B", fontSize:13, outline:"none" } as React.CSSProperties,
  input: { width:"100%", padding:"10px 14px", borderRadius:8, border:"1px solid #E8E4F0", background:"#FFFFFF", color:"#1E1B4B", fontSize:13, outline:"none" } as React.CSSProperties,
  table: { width:"100%", borderCollapse:"collapse" as const, fontSize:13 } as React.CSSProperties,
  th: { textAlign:"left" as const, padding:"10px 12px", borderBottom:"2px solid #E8E4F0", color:"#6B7280", fontWeight:600, fontSize:11, textTransform:"uppercase" as const, letterSpacing:"0.05em" } as React.CSSProperties,
  td: { padding:"10px 12px", borderBottom:"1px solid #F3F0FF" } as React.CSSProperties,
  tooltip: { background:"#FFFFFF", border:"1px solid #E8E4F0", borderRadius:8, fontSize:12, boxShadow:"0 4px 12px rgba(0,0,0,0.08)" },
};

// ═══════════════════════════════════════════════════════════════════════════════
//  COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════
const Metric = ({label,value,delta,accent=P[500]}:{label:string,value:string|number,delta?:string,accent?:string}) => (
  <div style={css.metricCard(accent)}>
    <div style={css.metricLabel}>{label}</div>
    <div style={css.metricVal}>{typeof value==="number"?value.toLocaleString():value}</div>
    {delta && <div style={css.metricDelta}>{delta}</div>}
  </div>
);

const Card = ({title,children,style={}}:{title?:string,children:React.ReactNode,style?:React.CSSProperties}) => (
  <div style={{...css.card,...style}}>
    {title && <div style={css.h3}>{title}</div>}
    {children}
  </div>
);

const SubTabs = ({tabs,active,onChange}:{tabs:{key:string,label:string}[],active:string,onChange:(t:string)=>void}) => (
  <div style={css.tabs}>{tabs.map(t=>(
    <button key={t.key} style={css.tabBtn(active===t.key)} onClick={()=>onChange(t.key)}>{t.label}</button>
  ))}</div>
);

const HBar = ({items,color,maxVal,showPct=false,total=0}:{items:[string,number][],color:string,maxVal?:number,showPct?:boolean,total?:number}) => {
  const mx = maxVal || Math.max(...items.map(i=>i[1]),1);
  return <div>{items.map(([name,count])=>(
    <div key={name} style={{display:"flex",alignItems:"center",gap:8,marginBottom:5}}>
      <div style={{width:150,fontSize:12,color:"#6B7280",textAlign:"right",flexShrink:0,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}} title={name}>{name}</div>
      <div style={{flex:1,height:20,borderRadius:6,background:"#F3F0FF",overflow:"hidden"}}>
        <div style={{height:"100%",width:`${Math.max(count/mx*100,1)}%`,background:color,borderRadius:6,transition:"width 0.4s ease"}}/>
      </div>
      <div style={{width:55,fontSize:12,fontWeight:600,color:"#1E1B4B",textAlign:"right"}}>{count.toLocaleString()}</div>
      {showPct && total>0 && <div style={{width:40,fontSize:11,color:"#9CA3AF"}}>{(count/total*100).toFixed(1)}%</div>}
    </div>
  ))}</div>;
};

const Expander = ({title,badge,color=P[500],children,defaultOpen=false}:{title:string,badge?:string,color?:string,children:React.ReactNode,defaultOpen?:boolean}) => {
  const [open,setOpen] = useState(defaultOpen);
  return (
    <div style={{background:"#FFFFFF",border:`1px solid ${open?P[200]:"#E8E4F0"}`,borderRadius:10,marginBottom:8,overflow:"hidden",transition:"all 0.2s",boxShadow:open?"0 2px 8px rgba(124,58,237,0.08)":"none"}}>
      <div style={{padding:"12px 16px",cursor:"pointer",display:"flex",justifyContent:"space-between",alignItems:"center",fontSize:13.5,fontWeight:600,color:"#1E1B4B"}} onClick={()=>setOpen(!open)}>
        <span style={{display:"flex",alignItems:"center",gap:8}}><span style={{width:4,height:4,borderRadius:2,background:color,display:"inline-block"}}/>{title}</span>
        <span style={{display:"flex",gap:8,alignItems:"center"}}>
          {badge && <span style={css.pill}>{badge}</span>}
          <span style={{fontSize:12,color:"#9CA3AF",transition:"transform 0.2s",transform:open?"rotate(180deg)":"rotate(0)"}}>▾</span>
        </span>
      </div>
      {open && <div style={{padding:"0 16px 16px",fontSize:13,lineHeight:1.6,color:"#4B5563"}}>{children}</div>}
    </div>
  );
};

const DonutChart = ({data,colors}:{data:{name:string,value:number}[],colors:string[]}) => {
  const total = data.reduce((a,b)=>a+b.value,0);
  let cum = 0;
  const toRad = (d:number) => (d-90)*Math.PI/180;
  return (
    <div style={{display:"flex",alignItems:"center",gap:20}}>
      <svg viewBox="0 0 200 200" style={{width:180,flexShrink:0}}>
        {data.map((d,i) => {
          const angle = (d.value/total)*360;
          const s1=cum; cum+=angle;
          const r=85, cx=100, cy=100;
          const x1=cx+r*Math.cos(toRad(s1)), y1=cy+r*Math.sin(toRad(s1));
          const x2=cx+r*Math.cos(toRad(s1+angle-0.5)), y2=cy+r*Math.sin(toRad(s1+angle-0.5));
          return <path key={i} d={`M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${angle>180?1:0} 1 ${x2} ${y2} Z`} fill={colors[i%colors.length]} stroke="#fff" strokeWidth={2}><title>{d.name}: {d.value.toLocaleString()} ({(d.value/total*100).toFixed(1)}%)</title></path>;
        })}
        <circle cx={100} cy={100} r={55} fill="#FFFFFF"/>
        <text x={100} y={96} textAnchor="middle" fill={P[800]} fontSize={20} fontWeight={800}>{total>=1000?(total/1000).toFixed(1)+"k":total.toLocaleString()}</text>
        <text x={100} y={112} textAnchor="middle" fill="#9CA3AF" fontSize={9} fontWeight={600}>TOTAL</text>
      </svg>
      <div style={{fontSize:12}}>
        {data.map((d,i) => (
          <div key={d.name} style={{display:"flex",alignItems:"center",gap:8,padding:"3px 0"}}>
            <span style={{width:10,height:10,borderRadius:3,background:colors[i%colors.length],flexShrink:0}}/>
            <span style={{color:"#4B5563",flex:1}}>{d.name}</span>
            <span style={{fontWeight:600,color:"#1E1B4B"}}>{d.value.toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
//  PAGES
// ═══════════════════════════════════════════════════════════════════════════════
const OverviewPage = () => {
  const yd = Object.entries(DATA.yearly_counts).map(([y,c])=>({year:+y,count:c})).sort((a,b)=>a.year-b.year);
  const cum = yd.reduce<{year:number,cum:number}[]>((a,d)=>{a.push({year:d.year,cum:(a.length?a[a.length-1].cum:0)+d.count});return a;},[]);
  const peak = yd.reduce((a,b)=>b.count>a.count?b:a,yd[0]);
  const sumPapers = yd.reduce((a,b)=>a+b.count,0);
  return <>
    <div style={css.h1}>❤️ Atherosclerosis & Lipoproteins Research</div>
    <div style={css.sub}>AI-Powered Knowledge Extraction — {sumPapers.toLocaleString()} papers (2020–2024)</div>
    <div style={css.grid(4)}>
      <Metric label="Total Publications" value={sumPapers} delta={`+${DATA.yearly_counts["2024"]} in 2024`}/>
      <Metric label="Years Covered" value="2020–2024" delta="5 years" accent={SKY[500]}/>
      <Metric label="Peak Year" value={peak.year} delta={`${peak.count.toLocaleString()} papers`} accent={EMERALD[500]}/>
      <Metric label="Avg per Year" value={Math.round(sumPapers/5)} accent={AMBER[500]}/>
    </div>
    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
      <Card title="📈 Publications by Year">
        <Recharts.ResponsiveContainer width="100%" height={220}>
          <Recharts.BarChart data={yd}><Recharts.XAxis dataKey="year" stroke="#9CA3AF" fontSize={11}/><Recharts.YAxis stroke="#9CA3AF" fontSize={11}/><Recharts.Tooltip contentStyle={css.tooltip}/><Recharts.Bar dataKey="count" fill={P[500]} radius={[6,6,0,0]}/></Recharts.BarChart>
        </Recharts.ResponsiveContainer>
      </Card>
      <Card title="📈 Cumulative Publications">
        <Recharts.ResponsiveContainer width="100%" height={220}>
          <Recharts.AreaChart data={cum}><Recharts.XAxis dataKey="year" stroke="#9CA3AF" fontSize={11}/><Recharts.YAxis stroke="#9CA3AF" fontSize={11}/><Recharts.Tooltip contentStyle={css.tooltip}/><Recharts.Area type="monotone" dataKey="cum" stroke={P[500]} fill={P[100]} strokeWidth={2.5}/></Recharts.AreaChart>
        </Recharts.ResponsiveContainer>
      </Card>
    </div>
    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14,marginTop:14}}>
      <Card title="🧬 Top 10 Lipoproteins">
        <HBar items={DATA.entity_stats.lipoprotein.top_20.slice(0,10)} color={P[500]}/>
      </Card>
      <Card title="🔬 Top 10 Biomarkers">
        <HBar items={DATA.entity_stats.biomarker.top_20.slice(0,10)} color={TEAL[500]}/>
      </Card>
    </div>
    <div style={css.h2}>📊 Entity Coverage</div>
    <div style={css.grid(4)}>
      {Object.entries(DATA.entity_stats).slice(0,8).map(([k,v])=>(
        <div key={k} style={css.metricCard(TYPE_COLORS[k]||P[500])}>
          <div style={css.metricLabel}>{k.replace(/_/g," ")}</div>
          <div style={{fontSize:18,fontWeight:700,color:"#1E1B4B"}}>{v.pubs_with_data.toLocaleString()}</div>
          <div style={{fontSize:11,color:"#9CA3AF"}}>{v.coverage_pct}% · {v.total_mentions.toLocaleString()} mentions · {v.unique} unique</div>
        </div>
      ))}
    </div>
  </>;
};

const TrendsPage = () => {
  const [sel,setSel] = useState(["lipoprotein:LDL","lipoprotein:HDL","lipoprotein:Lp(a)","gene:PCSK9"]);
  const allKeys = Object.keys(DATA.entity_yearly_trends);
  const years = ["2020","2021","2022","2023","2024"];
  const chartData = years.map(y=>{const r:any={year:+y};sel.forEach(k=>{r[k]=DATA.entity_yearly_trends[k]?.[y]||0;});return r;});
  return <>
    <div style={css.h1}>📅 Entity Trend Analysis</div>
    <div style={css.sub}>Track publication trends over time (2020–2024)</div>
    <div style={{marginBottom:16,display:"flex",flexWrap:"wrap",gap:6}}>
      {allKeys.map(k=>{const a=sel.includes(k);const[type,name]=k.split(":");return <button key={k} onClick={()=>setSel(p=>a?p.filter(x=>x!==k):[...p,k])} style={{...css.tag(a?TYPE_COLORS[type]||P[500]:"#D1D5DB"),cursor:"pointer",border:"none",opacity:a?1:0.5,fontSize:12,padding:"4px 12px"}}>{name}</button>;})}
    </div>
    <Card title="📈 Comparative Trend Lines">
      <Recharts.ResponsiveContainer width="100%" height={360}>
        <Recharts.LineChart data={chartData}><Recharts.XAxis dataKey="year" stroke="#9CA3AF" fontSize={11}/><Recharts.YAxis stroke="#9CA3AF" fontSize={11}/><Recharts.Tooltip contentStyle={css.tooltip}/><Recharts.Legend wrapperStyle={{fontSize:12}}/>
          {sel.map((k,i)=><Recharts.Line key={k} type="monotone" dataKey={k} name={k.split(":")[1]} stroke={CHART_PALETTE[i%CHART_PALETTE.length]} strokeWidth={2.5} dot={{r:4}}/>)}
        </Recharts.LineChart>
      </Recharts.ResponsiveContainer>
    </Card>
    <Card title="📊 Stacked Area" style={{marginTop:14}}>
      <Recharts.ResponsiveContainer width="100%" height={280}>
        <Recharts.AreaChart data={chartData}><Recharts.XAxis dataKey="year" stroke="#9CA3AF" fontSize={11}/><Recharts.YAxis stroke="#9CA3AF" fontSize={11}/><Recharts.Tooltip contentStyle={css.tooltip}/>
          {sel.map((k,i)=><Recharts.Area key={k} type="monotone" dataKey={k} name={k.split(":")[1]} stackId="1" stroke={CHART_PALETTE[i%CHART_PALETTE.length]} fill={`${CHART_PALETTE[i%CHART_PALETTE.length]}30`}/>)}
        </Recharts.AreaChart>
      </Recharts.ResponsiveContainer>
    </Card>
  </>;
};

const FieldAnalysisPage = () => {
  const [tab,setTab] = useState("top");
  const etypes = ["lipoprotein","biomarker","gene","protein","drug","risk_factor","comorbidity","pathophysiology"];
  return <>
    <div style={css.h1}>📊 Field Analysis & Correlations</div>
    <div style={css.sub}>Comprehensive analysis of all extracted entity fields</div>
    <SubTabs tabs={[{key:"top",label:"Top Entities"},{key:"corr",label:"Correlations"},{key:"extra",label:"Comorbidities & Pathways"}]} active={tab} onChange={setTab}/>
    {tab==="top" && <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
      {etypes.map(et=>{const st=DATA.entity_stats[et];if(!st)return null;return <Card key={et} title={`${et.replace(/_/g," ")} — Top 15`}><HBar items={st.top_20.slice(0,15)} color={TYPE_COLORS[et]||P[500]}/></Card>;})}
    </div>}
    {tab==="corr" && <>
      <div style={css.grid(3)}><Metric label="Total Correlations" value={DATA.correlations.total}/><Metric label="Unique" value={DATA.correlations.unique} accent={SKY[500]}/><Metric label="Papers w/ Correlations" value={148} accent={EMERALD[500]}/></div>
      <Card title="Top Correlations Extracted">
        <table style={css.table}><thead><tr><th style={css.th}>#</th><th style={css.th}>Correlation</th><th style={css.th}>Freq</th></tr></thead><tbody>{DATA.correlations.top_30.map(([t,c],i)=><tr key={i}><td style={css.td}>{i+1}</td><td style={{...css.td,maxWidth:600}}>{t}</td><td style={{...css.td,fontWeight:600}}>{c}</td></tr>)}</tbody></table>
      </Card>
    </>}
    {tab==="extra" && <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
      <Card title="🏥 Top Comorbidities"><DonutChart data={DATA.entity_stats.comorbidity.top_20.slice(0,8).map(([n,v])=>({name:n,value:v}))} colors={CHART_PALETTE}/></Card>
      <Card title="📚 Thematic Categories"><DonutChart data={DATA.entity_stats.thematic_category.top_20.slice(0,8).map(([n,v])=>({name:n,value:v}))} colors={[...CHART_PALETTE].reverse()}/></Card>
      <Card title="🔬 Top Pathophysiology" style={{gridColumn:"1/-1"}}><HBar items={DATA.entity_stats.pathophysiology.top_20.slice(0,15)} color={P[400]}/></Card>
    </div>}
  </>;
};

const DrugsPage = () => {
  const catData = Object.entries(DATA.drug_categories).map(([n,v])=>({name:n,value:v}));
  return <>
    <div style={css.h1}>💊 Drugs & Categories</div>
    <div style={css.sub}>{DATA.entity_stats.drug.unique} unique drugs · {DATA.entity_stats.drug.total_mentions.toLocaleString()} mentions · 7 categories</div>
    <div style={css.grid(3)}><Metric label="Drug Mentions" value={DATA.entity_stats.drug.total_mentions} accent={P[600]}/><Metric label="Unique Drugs" value={174} accent={SKY[500]}/><Metric label="Papers with Drugs" value={DATA.entity_stats.drug.pubs_with_data} delta={`${DATA.entity_stats.drug.coverage_pct}% coverage`} accent={EMERALD[500]}/></div>
    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
      <Card title="Drug Categories"><DonutChart data={catData} colors={[P[500],TEAL[500],SKY[500],EMERALD[500],AMBER[500],ROSE[500],"#9CA3AF"]}/></Card>
      <Card title="Top 20 Drugs"><HBar items={DATA.entity_stats.drug.top_20} color={P[600]}/></Card>
    </div>
  </>;
};

const SPECIFIC_RELATIONSHIPS = [
  { source: "LDL", target: "Coronary Artery Disease", type: "associated_with", count: 2847, sourceType: "lipoprotein", targetType: "comorbidity" },
  { source: "PCSK9", target: "LDL-C", type: "modulates", count: 1523, sourceType: "gene", targetType: "lipoprotein" },
  { source: "Statins", target: "LDL", type: "reduces", count: 1456, sourceType: "drug", targetType: "lipoprotein" },
  { source: "Hypertension", target: "Stroke", type: "risk_factor_for", count: 1234, sourceType: "risk_factor", targetType: "comorbidity" },
  { source: "HDL", target: "Cardiovascular Events", type: "reduces", count: 1189, sourceType: "lipoprotein", targetType: "clinical_outcome" },
  { source: "CRP", target: "Inflammation", type: "marker_for", count: 987, sourceType: "biomarker", targetType: "pathophysiology" },
  { source: "Ezetimibe", target: "LDL-C", type: "reduces", count: 856, sourceType: "drug", targetType: "lipoprotein" },
  { source: "Diabetes", target: "Atherosclerosis", type: "risk_factor_for", count: 823, sourceType: "risk_factor", targetType: "comorbidity" },
  { source: "APOE", target: "Lipid Metabolism", type: "involved_in", count: 756, sourceType: "gene", targetType: "pathophysiology" },
  { source: "Smoking", target: "Endothelial Dysfunction", type: "associated_with", count: 698, sourceType: "risk_factor", targetType: "pathophysiology" },
  { source: "Lp(a)", target: "Cardiovascular Risk", type: "increases", count: 645, sourceType: "lipoprotein", targetType: "clinical_outcome" },
  { source: "IL-6", target: "Plaque Formation", type: "promotes", count: 534, sourceType: "biomarker", targetType: "pathophysiology" },
  { source: "Evolocumab", target: "PCSK9", type: "inhibits", count: 478, sourceType: "drug", targetType: "gene" },
  { source: "Oxidative Stress", target: "Foam Cell Formation", type: "mechanism_of", count: 423, sourceType: "pathophysiology", targetType: "pathophysiology" },
  { source: "Triglycerides", target: "Metabolic Syndrome", type: "associated_with", count: 398, sourceType: "lipoprotein", targetType: "comorbidity" },
];

const RelationshipsPage = () => (
  <>
    <div style={css.h1}>🔗 Extracted Relationships</div>
    <div style={css.sub}>{DATA.relationships.total.toLocaleString()} relationships extracted from {DATA.relationships.papers_with.toLocaleString()} papers</div>
    <div style={css.grid(3)}><Metric label="Total Relationships" value={DATA.relationships.total}/><Metric label="Papers with Relationships" value={DATA.relationships.papers_with} delta={`${(DATA.relationships.papers_with/DATA.total_papers*100).toFixed(1)}%`} accent={SKY[500]}/><Metric label="Relationship Types" value={14} accent={EMERALD[500]}/></div>
    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
      <Card title="Relationship Types"><HBar items={Object.entries(DATA.relationships.types).map(([n,v])=>[n,v] as [string,number])} color={P[500]}/></Card>
      <Card title="Top Entity Pair Types"><HBar items={Object.entries(DATA.relationships.top_pairs).map(([n,v])=>[n,v] as [string,number])} color={TEAL[500]}/></Card>
    </div>
    
    <div style={css.h2}>🔬 Specific Relationships Extracted</div>
    <Card>
      <table style={css.table}>
        <thead>
          <tr>
            <th style={css.th}>Source</th>
            <th style={css.th}>Relationship</th>
            <th style={css.th}>Target</th>
            <th style={css.th}>Count</th>
          </tr>
        </thead>
        <tbody>
          {SPECIFIC_RELATIONSHIPS.map((rel, i) => (
            <tr key={i}>
              <td style={css.td}>
                <span style={{display:"flex",alignItems:"center",gap:6}}>
                  <span style={{width:8,height:8,borderRadius:2,background:TYPE_COLORS[rel.sourceType]||P[500]}}/>
                  <span style={{fontWeight:600}}>{rel.source}</span>
                </span>
              </td>
              <td style={{...css.td,color:P[600],fontStyle:"italic"}}>{rel.type.replace(/_/g," ")}</td>
              <td style={css.td}>
                <span style={{display:"flex",alignItems:"center",gap:6}}>
                  <span style={{width:8,height:8,borderRadius:2,background:TYPE_COLORS[rel.targetType]||P[500]}}/>
                  <span style={{fontWeight:600}}>{rel.target}</span>
                </span>
              </td>
              <td style={{...css.td,fontWeight:700,color:P[700]}}>{rel.count.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  </>
);

// ═══════════════════════════════════════════════════════════════════════════════
//  ENTITIES PAGE (Full Entity Resolution)
// ═══════════════════════════════════════════════════════════════════════════════
const EntitiesPage = () => {
  const [tab,setTab] = useState("overview");
  const [typeFilter,setTypeFilter] = useState("All");
  const [search,setSearch] = useState("");

  const groups = DATA.er_groups;
  const totalMentions = Object.values(DATA.entity_stats).reduce((a,s)=>a+s.total_mentions,0);
  const totalUnique = Object.values(DATA.entity_stats).reduce((a,s)=>a+s.unique,0);
  const totalVariants = groups.reduce((a,g)=>a+g.variants.length,0);
  const totalCanonical = groups.length;
  const totalUnified = groups.reduce((a,g)=>a+g.total_mentions,0);
  const totalFP = DATA.er_false_positives.reduce((a,f)=>a+f.count,0);

  const filtered = useMemo(()=>{
    let f = groups;
    if(typeFilter!=="All") f=f.filter(g=>g.type===typeFilter);
    if(search.trim()){const q=search.toLowerCase();f=f.filter(g=>g.canonical_name.toLowerCase().includes(q)||g.variants.some(v=>v.name.toLowerCase().includes(q)));}
    return f;
  },[typeFilter,search]);

  const types = [...new Set(groups.map(g=>g.type))].sort();

  return <>
    <div style={css.h1}>🧬 Entities</div>
    <div style={css.sub}>Identifying and merging variant entity names across {DATA.total_papers.toLocaleString()} papers. Different strings that refer to the same real-world entity are mapped to one canonical form.</div>

    <SubTabs tabs={[{key:"overview",label:"Overview"},{key:"groups",label:"Resolution Groups"},{key:"fp",label:"False Positives"},{key:"conflicts",label:"Cross-Type Conflicts"},{key:"analysis",label:"Analysis"}]} active={tab} onChange={setTab}/>

    {tab==="overview" && <>
      <div style={css.grid(5)}>
        <Metric label="Entity Mentions" value={totalMentions}/>
        <Metric label="Unique Strings" value={totalUnique} accent={SKY[500]}/>
        <Metric label="Variants Resolved" value={totalVariants} delta={`→ ${totalCanonical} canonical`} accent={EMERALD[500]}/>
        <Metric label="Mentions Unified" value={totalUnified} delta={`${(totalUnified/totalMentions*100).toFixed(1)}%`} accent={P[400]}/>
        <Metric label="False Positives" value={totalFP} delta="in protein category" accent={AMBER[500]}/>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
        <Card title="📊 Entity Type Distribution">
          <DonutChart data={Object.entries(DATA.entity_stats).filter(([k])=>!["clinical_outcome","therapeutic_intervention","thematic_category"].includes(k)).map(([k,v])=>({name:k.replace(/_/g," "),value:v.total_mentions}))} colors={Object.keys(DATA.entity_stats).filter(k=>!["clinical_outcome","therapeutic_intervention","thematic_category"].includes(k)).map(k=>TYPE_COLORS[k]||P[500])}/>
        </Card>
        <Card title="🔝 Top 15 Entities (All Types)">
          {(()=>{const all:[string,number][]=[]; Object.entries(DATA.entity_stats).forEach(([,st])=>st.top_20.slice(0,5).forEach(e=>all.push(e))); all.sort((a,b)=>b[1]-a[1]); return <HBar items={all.slice(0,15)} color={P[500]}/>;})()}
        </Card>
      </div>
      <Card title="🔄 Resolution Impact — Top 15 Groups" style={{marginTop:14}}>
        <HBar items={groups.slice(0,15).map(g=>[`${g.canonical_name} (${g.type})`,g.total_mentions] as [string,number])} color={P[500]}/>
      </Card>
    </>}

    {tab==="groups" && <>
      <div style={{display:"flex",gap:12,marginBottom:16}}>
        <select style={css.select} value={typeFilter} onChange={e=>setTypeFilter(e.target.value)}>
          <option value="All">All types</option>
          {types.map(t=><option key={t} value={t}>{t}</option>)}
        </select>
        <input style={{...css.input,maxWidth:300}} placeholder="Search entity…" value={search} onChange={e=>setSearch(e.target.value)}/>
        <span style={{fontSize:12,color:"#9CA3AF",alignSelf:"center"}}>{filtered.length} groups</span>
      </div>
      {filtered.map((g,i)=>(
        <Expander key={g.canonical_id+g.canonical_name} defaultOpen={i<3} color={TYPE_COLORS[g.type]||P[500]}
          title={g.canonical_name} badge={`${g.total_mentions.toLocaleString()} mentions · ${g.variants.length} variants`}>
          <div style={{display:"flex",gap:8,marginBottom:12}}>
            <span style={css.tag(TYPE_COLORS[g.type]||P[500])}>{g.type}</span>
            <span style={css.pill}>{g.canonical_id}</span>
          </div>
          <HBar items={g.variants.map(v=>[v.name,v.count] as [string,number])} color={TYPE_COLORS[g.type]||P[500]}/>
          <div style={{marginTop:10,padding:"10px 14px",background:"#F0FDF4",borderRadius:8,fontSize:12,color:"#166534",border:"1px solid #BBF7D0"}}>
            ✅ <strong>RESOLVED:</strong> {g.variants.length} string variants → 1 canonical entity <code style={{background:"#DCFCE7",padding:"1px 6px",borderRadius:4}}>{g.canonical_id}</code>
          </div>
        </Expander>
      ))}
    </>}

    {tab==="fp" && <>
      <div style={css.h2}>⚠️ False Positives in Protein Category</div>
      <div style={css.sub}>These strings were incorrectly classified as proteins. They should be reclassified or removed.</div>
      <div style={css.grid(3)}>
        <Metric label="False Positive Mentions" value={totalFP} accent={AMBER[500]}/>
        <Metric label="Total Protein Mentions" value={DATA.total_protein_mentions} accent={TEAL[500]}/>
        <Metric label="Error Rate" value={`${(totalFP/DATA.total_protein_mentions*100).toFixed(1)}%`} delta="of protein mentions" accent={ROSE[500]}/>
      </div>
      <Card title="False Positive Terms">
        {DATA.er_false_positives.map(fp=>(
          <div key={fp.term} style={{display:"flex",alignItems:"center",gap:12,padding:"10px 0",borderBottom:"1px solid #F3F0FF"}}>
            <span style={{fontSize:16}}>{fp.should_be==="lipoprotein"?"🔶":"🔴"}</span>
            <code style={{fontWeight:700,fontSize:14,color:P[800],minWidth:90,fontFamily:"'SF Mono','Fira Code',monospace"}}>{fp.term}</code>
            <div style={{flex:1,height:22,borderRadius:6,background:"#F3F0FF",overflow:"hidden"}}>
              <div style={{height:"100%",width:`${fp.count/DATA.er_false_positives[0].count*100}%`,background:fp.should_be==="lipoprotein"?AMBER[500]:ROSE[500],borderRadius:6}}/>
            </div>
            <span style={{fontSize:13,fontWeight:700,minWidth:50,textAlign:"right"}}>{fp.count.toLocaleString()}</span>
            <span style={css.tag(fp.should_be==="lipoprotein"?AMBER[500]:ROSE[500])}>{fp.should_be==="lipoprotein"?"→ lipoprotein":"NOT AN ENTITY"}</span>
          </div>
        ))}
      </Card>
      <div style={{marginTop:16,padding:16,background:"#FFFBEB",borderRadius:10,border:"1px solid #FDE68A",fontSize:13}}>
        <strong style={{color:"#92400E"}}>⚠️ Recommended Action:</strong>{" "}
        <span style={{color:"#78350F"}}>Remove non-entities (follow-up, high-fat, THP-1). Reclassify lipoprotein terms (LDL-C, HDL-C, ox-LDL, non-HDL) from proteins to lipoproteins.</span>
      </div>
    </>}

    {tab==="conflicts" && <>
      <div style={css.h2}>⚡ Cross-Type Conflicts</div>
      <div style={css.sub}>Entities appearing in multiple categories. Some are legitimate (IL-6 is both a protein and biomarker), others indicate extraction errors.</div>
      <div style={css.grid(3)}>
        <Metric label="Total Conflicts" value={DATA.er_conflicts.length} accent={ROSE[500]}/>
        <Metric label="3+ Types" value={DATA.er_conflicts.filter(c=>c.types.length>=3).length} delta="high ambiguity" accent={AMBER[500]}/>
        <Metric label="Total Mentions" value={DATA.er_conflicts.reduce((a,c)=>a+c.total_mentions,0)} accent={P[500]}/>
      </div>
      <Card title="Cross-Type Entities">
        <table style={css.table}><thead><tr><th style={css.th}>Entity</th><th style={css.th}>Types</th><th style={css.th}>Total Mentions</th></tr></thead>
        <tbody>{DATA.er_conflicts.map(c=>(
          <tr key={c.entity}><td style={{...css.td,fontWeight:600}}>{c.entity}</td><td style={css.td}>{c.types.map(t=><span key={t} style={css.tag(TYPE_COLORS[t]||P[500])}>{t}</span>)}</td><td style={{...css.td,fontWeight:600}}>{c.total_mentions.toLocaleString()}</td></tr>
        ))}</tbody></table>
      </Card>
    </>}

    {tab==="analysis" && <>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
        <Card title="📅 Entity Trends Over Time">
          {(()=>{
            const years=["2020","2021","2022","2023","2024"];
            const keys=["lipoprotein:LDL","lipoprotein:HDL","gene:PCSK9","biomarker:CRP"];
            const cd=years.map(y=>{const r:any={year:+y};keys.forEach(k=>{r[k]=DATA.entity_yearly_trends[k]?.[y]||0});return r;});
            return <Recharts.ResponsiveContainer width="100%" height={280}>
              <Recharts.LineChart data={cd}><Recharts.XAxis dataKey="year" stroke="#9CA3AF" fontSize={11}/><Recharts.YAxis stroke="#9CA3AF" fontSize={11}/><Recharts.Tooltip contentStyle={css.tooltip}/><Recharts.Legend wrapperStyle={{fontSize:11}}/>
                {keys.map((k,i)=><Recharts.Line key={k} type="monotone" dataKey={k} name={k.split(":")[1]} stroke={CHART_PALETTE[i]} strokeWidth={2} dot={{r:3}}/>)}
              </Recharts.LineChart>
            </Recharts.ResponsiveContainer>;
          })()}
        </Card>
        <Card title="Before vs After Resolution">
          <div style={{fontSize:13,lineHeight:2}}>
            <div style={{display:"flex",justifyContent:"space-between",padding:"6px 0",borderBottom:"1px solid #F3F0FF",fontWeight:600,color:"#6B7280"}}><span>Metric</span><span>Before</span><span>After</span></div>
            <div style={{display:"flex",justifyContent:"space-between",padding:"6px 0",borderBottom:"1px solid #F3F0FF"}}><span>Unique entity strings</span><span style={{fontWeight:600}}>{totalUnique.toLocaleString()}</span><span style={{fontWeight:600,color:EMERALD[500]}}>{(totalUnique-totalVariants+totalCanonical).toLocaleString()}</span></div>
            <div style={{display:"flex",justifyContent:"space-between",padding:"6px 0",borderBottom:"1px solid #F3F0FF"}}><span>Resolution groups</span><span style={{fontWeight:600}}>—</span><span style={{fontWeight:600,color:P[600]}}>{totalCanonical}</span></div>
            <div style={{display:"flex",justifyContent:"space-between",padding:"6px 0",borderBottom:"1px solid #F3F0FF"}}><span>Mentions unified</span><span style={{fontWeight:600}}>0</span><span style={{fontWeight:600,color:P[600]}}>{totalUnified.toLocaleString()}</span></div>
            <div style={{display:"flex",justifyContent:"space-between",padding:"6px 0"}}><span>False positives flagged</span><span style={{fontWeight:600}}>0</span><span style={{fontWeight:600,color:AMBER[500]}}>{totalFP.toLocaleString()}</span></div>
          </div>
        </Card>
      </div>
    </>}
  </>;
};

// ═══════════════════════════════════════════════════════════════════════════════
//  AI AGENT PAGE
// ═══════════════════════════════════════════════════════════════════════════════
const AIAgentPage = () => {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<{answer:string,sources:any[]}|null>(null);
  const [error, setError] = useState<string|null>(null);

  const handleQuery = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    setError(null);
    setResponse(null);
    
    try {
      const res = await fetch("http://localhost:8000/athero/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, num_sources: 5 })
      });
      
      if (!res.ok) throw new Error("Failed to query");
      
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setResponse({ answer: data.answer, sources: data.sources });
      }
    } catch (err: any) {
      setError(err.message || "Failed to connect to API");
    } finally {
      setLoading(false);
    }
  };

  return <>
    <div style={css.h1}>🤖 AI Literature Agent</div>
    <div style={css.sub}>Ask questions about atherosclerosis research based on {DATA.total_papers.toLocaleString()} analyzed papers (GPT-4o-mini)</div>
    
    <Card style={{marginBottom:20}}>
      <div style={{display:"flex",gap:12}}>
        <input
          style={{...css.input,flex:1}}
          placeholder="e.g., How do PCSK9 inhibitors affect LDL cholesterol levels?"
          value={query}
          onChange={e=>setQuery(e.target.value)}
          onKeyDown={e=>e.key==="Enter"&&handleQuery()}
        />
        <button
          onClick={handleQuery}
          disabled={loading || !query.trim()}
          style={{
            padding:"10px 24px",
            borderRadius:8,
            border:"none",
            background:loading?"#9CA3AF":`linear-gradient(135deg, ${P[500]}, ${P[700]})`,
            color:"white",
            fontWeight:600,
            cursor:loading?"wait":"pointer",
            transition:"all 0.2s"
          }}
        >
          {loading ? "Analyzing..." : "🔍 Ask"}
        </button>
      </div>
      
      <div style={{marginTop:16,display:"flex",flexWrap:"wrap",gap:8}}>
        <span style={{fontSize:11,color:"#9CA3AF"}}>Try:</span>
        {["What are the main risk factors for atherosclerosis?","How does inflammation contribute to plaque formation?","What role does Lp(a) play in cardiovascular disease?","Compare statins vs PCSK9 inhibitors for LDL reduction"].map(q=>(
          <button key={q} onClick={()=>setQuery(q)} style={{...css.pill,cursor:"pointer",border:"none",background:"#F3F0FF"}}>{q}</button>
        ))}
      </div>
    </Card>
    
    {error && (
      <Card style={{background:"#FEF2F2",borderColor:"#FECACA",marginBottom:20}}>
        <div style={{color:"#DC2626",fontSize:14}}>❌ {error}</div>
      </Card>
    )}
    
    {response && (
      <>
        <Card title="📝 Answer" style={{marginBottom:20}}>
          <div style={{fontSize:14,lineHeight:1.8,whiteSpace:"pre-wrap"}}>{response.answer}</div>
        </Card>
        
        {response.sources.length > 0 && (
          <Card title={`📚 Sources (${response.sources.length} papers)`}>
            {response.sources.map((src,i)=>(
              <Expander key={i} title={src.title} badge={`${src.year} · PMID: ${src.pmid}`} color={P[500]} defaultOpen={i===0}>
                <div style={{fontSize:13}}>
                  <div style={{marginBottom:8}}><strong>Journal:</strong> {src.journal}</div>
                  {src.lipoproteins?.length > 0 && <div style={{marginBottom:4}}><strong>Lipoproteins:</strong> {src.lipoproteins.join(", ")}</div>}
                  {src.drugs?.length > 0 && <div style={{marginBottom:4}}><strong>Drugs:</strong> {src.drugs.join(", ")}</div>}
                  {src.correlations?.length > 0 && <div><strong>Key Findings:</strong> {src.correlations.join("; ")}</div>}
                  <a href={`https://pubmed.ncbi.nlm.nih.gov/${src.pmid}/`} target="_blank" rel="noopener noreferrer" style={{color:P[600],textDecoration:"underline",marginTop:8,display:"inline-block"}}>View on PubMed →</a>
                </div>
              </Expander>
            ))}
          </Card>
        )}
      </>
    )}
    
    {!response && !error && !loading && (
      <div style={{textAlign:"center",padding:40,color:"#9CA3AF"}}>
        <div style={{fontSize:48,marginBottom:16}}>🔬</div>
        <div style={{fontSize:14}}>Ask a question about atherosclerosis, lipoproteins, cardiovascular risk, or treatments</div>
      </div>
    )}
  </>;
};

// ═══════════════════════════════════════════════════════════════════════════════
//  MAIN APP
// ═══════════════════════════════════════════════════════════════════════════════
const TABS:{key:Tab,icon:string,label:string}[] = [
  {key:"overview",icon:"📊",label:"Overview"},
  {key:"trends",icon:"📅",label:"Entity Trends"},
  {key:"field_analysis",icon:"📈",label:"Field Analysis"},
  {key:"drugs",icon:"💊",label:"Drugs"},
  {key:"relationships",icon:"🔗",label:"Relationships"},
  {key:"entities",icon:"🧬",label:"Entities"},
  {key:"ai_agent",icon:"🤖",label:"AI Agent"},
];

export function AtheroscleresisDashboard(){
  const [tab,setTab] = useState<Tab>("overview");
  return (
    <div style={css.app}>
      <nav style={css.sidebar}>
        <div style={css.sidebarTitle}>❤️ Atherosclerosis<br/>& Lipoproteins</div>
        <div style={{padding:"0 24px 12px",fontSize:11,color:"#9CA3AF"}}>Research Analysis Dashboard</div>
        {TABS.map(t=>(
          <div key={t.key} style={css.navItem(tab===t.key)} onClick={()=>setTab(t.key)}>
            {t.icon}&nbsp;&nbsp;{t.label}
          </div>
        ))}
        <div style={{marginTop:"auto",padding:"16px 24px",fontSize:11,color:"#9CA3AF",borderTop:"1px solid #E8E4F0"}}>
          {Object.values(DATA.yearly_counts).reduce((a,b)=>a+b,0).toLocaleString()} papers · 2020–2024
        </div>
      </nav>
      <main style={css.main}>
        {tab==="overview"&&<OverviewPage/>}
        {tab==="trends"&&<TrendsPage/>}
        {tab==="field_analysis"&&<FieldAnalysisPage/>}
        {tab==="drugs"&&<DrugsPage/>}
        {tab==="relationships"&&<RelationshipsPage/>}
        {tab==="entities"&&<EntitiesPage/>}
        {tab==="ai_agent"&&<AIAgentPage/>}
      </main>
    </div>
  );
}
