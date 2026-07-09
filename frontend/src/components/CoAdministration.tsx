import { useState, useEffect } from "react";
import {
  Search, Plus, X, Loader2, ServerCrash, Pill, ShieldAlert, Atom,
  Activity, Stethoscope, AlertTriangle, CheckCircle2,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { searchDrugsAsync, waitForApiCheck, type Drug } from "@/lib/drugData";
import {
  checkCoAdministration, getCoAdminConditions,
  type CoAdminResult, type CoAdminHit, type ConditionOption,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const FALLBACK_CONDITIONS: ConditionOption[] = [
  { key: "pregnancy", label: "Pregnancy" },
  { key: "lactation", label: "Lactation / breastfeeding" },
  { key: "renal_impairment", label: "Renal impairment" },
  { key: "hepatic_impairment", label: "Hepatic impairment" },
  { key: "alcohol", label: "Alcohol consumption" },
  { key: "g6pd_deficiency", label: "G6PD deficiency" },
  { key: "myelosuppression", label: "Myelosuppression" },
  { key: "driving", label: "Driving / operating machinery" },
];

const SEVERITY_ORDER = ["severe", "moderate", "minor", "unknown"];

function severityStyles(severity: string) {
  switch (severity) {
    case "severe":
      return { badge: "bg-red-500 text-white", card: "bg-red-50 border-red-200 dark:bg-red-950/30 dark:border-red-800", text: "text-red-800 dark:text-red-300", label: "HIGH" };
    case "moderate":
      return { badge: "bg-amber-500 text-white", card: "bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-800/50", text: "text-amber-800 dark:text-amber-300", label: "MEDIUM" };
    case "minor":
      return { badge: "bg-green-500 text-white", card: "bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800", text: "text-green-800 dark:text-green-300", label: "LOW" };
    default:
      return { badge: "bg-gray-400 text-white", card: "bg-muted/30 border-border", text: "text-muted-foreground", label: "N/A" };
  }
}

export function CoAdministration() {
  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const [conditions, setConditions] = useState<ConditionOption[]>(FALLBACK_CONDITIONS);

  // Drug list
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Drug[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [drugs, setDrugs] = useState<string[]>([]);

  // Patient context
  const [sex, setSex] = useState<string>("");
  const [age, setAge] = useState<string>("");
  const [activeConditions, setActiveConditions] = useState<string[]>([]);
  const [diseaseInput, setDiseaseInput] = useState("");
  const [diseases, setDiseases] = useState<string[]>([]);

  // Result
  const [result, setResult] = useState<CoAdminResult | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<string[]>(["severe", "moderate", "minor"]);

  useEffect(() => {
    waitForApiCheck().then(setApiReady);
    getCoAdminConditions().then(setConditions).catch(() => setConditions(FALLBACK_CONDITIONS));
  }, []);

  const handleSearch = async (value: string) => {
    setQuery(value);
    if (value.length >= 2) {
      setIsSearching(true);
      try {
        setResults(await searchDrugsAsync(value));
      } catch {
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    } else {
      setResults([]);
    }
  };

  const addDrug = (name: string) => {
    if (name && !drugs.includes(name)) setDrugs([...drugs, name]);
    setQuery("");
    setResults([]);
    setResult(null);
  };

  const removeDrug = (name: string) => {
    setDrugs(drugs.filter((d) => d !== name));
    setResult(null);
  };

  const toggleCondition = (key: string) => {
    setActiveConditions((prev) =>
      prev.includes(key) ? prev.filter((c) => c !== key) : [...prev, key]
    );
    setResult(null);
  };

  const addDisease = () => {
    const term = diseaseInput.trim();
    if (term && !diseases.includes(term)) setDiseases([...diseases, term]);
    setDiseaseInput("");
    setResult(null);
  };

  const clearAll = () => {
    setDrugs([]);
    setActiveConditions([]);
    setDiseases([]);
    setSex("");
    setAge("");
    setResult(null);
  };

  const handleCheck = async () => {
    if (drugs.length === 0) return;
    setIsChecking(true);
    try {
      const res = await checkCoAdministration(drugs, {
        sex: sex || null,
        age: age ? parseInt(age, 10) : null,
        conditions: activeConditions,
        diseases,
      });
      setResult(res);
    } catch (error) {
      setResult({
        drugs, resolved_drugs: [], unresolved_drugs: drugs,
        patient: { sex, age: age ? parseInt(age, 10) : null, conditions: activeConditions, diseases },
        contraindications: [], interactions: [], adverse_effects: [],
        summary: `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
        disclaimer: "",
      });
    } finally {
      setIsChecking(false);
    }
  };

  const toggleSeverity = (s: string) => {
    setSeverityFilter((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  };

  const filterHits = (hits: CoAdminHit[]) =>
    hits
      .filter((h) => severityFilter.includes(h.severity) || h.severity === "unknown")
      .sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity));

  return (
    <div className="space-y-8">
      {apiReady === false && (
        <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/30 flex items-center gap-4">
          <ServerCrash className="h-8 w-8 text-destructive flex-shrink-0" />
          <div>
            <p className="font-semibold text-destructive">Backend API Not Available</p>
            <p className="text-sm text-muted-foreground">Please ensure the FastAPI server is running on http://localhost:8000</p>
          </div>
        </div>
      )}

      {/* Two-panel input, galinos-style */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* LEFT: Co-administered drugs */}
        <Card className="glass-card border-border">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-3 text-lg">
              <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary to-info flex items-center justify-center">
                <Pill className="h-4 w-4 text-white" />
              </div>
              <span>Co-administered drugs</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              {isSearching && <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground animate-spin" />}
              <Input
                placeholder="Trade name, active substance, barcode…"
                value={query}
                onChange={(e) => handleSearch(e.target.value)}
                className="pl-11 h-12 bg-card/80 border-border/50 rounded-xl"
              />
              <AnimatePresence>
                {results.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
                    className="absolute top-full left-0 right-0 mt-2 z-50 glass-card rounded-xl overflow-hidden max-h-64 overflow-y-auto"
                  >
                    {results.slice(0, 8).map((drug) => (
                      <button
                        key={drug.id}
                        onClick={() => addDrug(drug.name)}
                        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-primary/5 transition-colors text-left text-sm border-b border-border/30 last:border-0"
                      >
                        <Pill className="h-4 w-4 text-primary" />
                        <span className="font-medium">{drug.name}</span>
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {drugs.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {drugs.map((name) => (
                  <span key={name} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary/10 text-sm font-medium">
                    {name}
                    <button onClick={() => removeDrug(name)} className="text-muted-foreground hover:text-destructive">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Add one or more drugs to check.</p>
            )}
          </CardContent>
        </Card>

        {/* RIGHT: Patient details (optional) */}
        <Card className="glass-card border-border">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-3 text-lg">
              <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-accent to-info flex items-center justify-center">
                <Stethoscope className="h-4 w-4 text-white" />
              </div>
              <span>Patient details (optional)</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <label className="text-sm text-muted-foreground">Sex</label>
                <select
                  value={sex}
                  onChange={(e) => { setSex(e.target.value); setResult(null); }}
                  className="h-9 rounded-lg border border-border/50 bg-card/80 px-2 text-sm"
                >
                  <option value="">—</option>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm text-muted-foreground">Age (yrs)</label>
                <Input
                  type="number" min={0} max={120} value={age}
                  onChange={(e) => { setAge(e.target.value); setResult(null); }}
                  className="h-9 w-20 bg-card/80 border-border/50 rounded-lg"
                />
              </div>
            </div>

            <div>
              <p className="text-sm font-medium text-muted-foreground mb-2">Special conditions</p>
              <div className="grid grid-cols-2 gap-2">
                {conditions.map((c) => (
                  <button
                    key={c.key}
                    onClick={() => toggleCondition(c.key)}
                    className={cn(
                      "px-3 py-2 rounded-lg border text-xs font-medium transition-colors text-center",
                      activeConditions.includes(c.key)
                        ? "bg-primary text-white border-primary"
                        : "bg-card/60 border-border/50 text-muted-foreground hover:border-primary/50"
                    )}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-sm font-medium text-muted-foreground mb-2">Diseases, diagnoses, symptoms</p>
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Type a condition and press Enter…"
                  value={diseaseInput}
                  onChange={(e) => setDiseaseInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addDisease(); } }}
                  className="pl-11 h-10 bg-card/80 border-border/50 rounded-lg"
                />
              </div>
              {diseases.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {diseases.map((d) => (
                    <span key={d} className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-muted text-xs">
                      {d}
                      <button onClick={() => { setDiseases(diseases.filter((x) => x !== d)); setResult(null); }} className="text-muted-foreground hover:text-destructive">
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Actions */}
      <div className="flex gap-4">
        <Button
          onClick={handleCheck}
          disabled={drugs.length === 0 || isChecking}
          className="flex-1 h-14 text-base font-semibold bg-gradient-to-r from-primary to-accent hover:opacity-90 btn-shine rounded-xl"
        >
          {isChecking ? (
            <><Loader2 className="h-5 w-5 mr-2 animate-spin" />Checking…</>
          ) : (
            <><ShieldAlert className="h-5 w-5 mr-2" />Check co-administration</>
          )}
        </Button>
        <Button variant="outline" onClick={clearAll} disabled={isChecking} className="h-14 px-6 rounded-xl border-border/50">
          Clear all
        </Button>
      </div>

      {/* Results */}
      <AnimatePresence mode="wait">
        {result && (
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -30 }} className="space-y-6">
            {/* Summary + disclaimer */}
            <Card className="glass-card border-border">
              <CardContent className="p-6 space-y-3">
                <p className="text-sm text-foreground">{result.summary}</p>
                {result.unresolved_drugs.length > 0 && (
                  <p className="text-xs text-amber-600 dark:text-amber-400">
                    Not found: {result.unresolved_drugs.join(", ")}
                  </p>
                )}
                {result.disclaimer && (
                  <p className="text-xs text-muted-foreground border-t border-border/50 pt-3 flex items-start gap-2">
                    <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                    {result.disclaimer}
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Severity filter */}
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="text-muted-foreground self-center mr-1">Filter:</span>
              {["severe", "moderate", "minor"].map((s) => {
                const st = severityStyles(s);
                const active = severityFilter.includes(s);
                return (
                  <button
                    key={s}
                    onClick={() => toggleSeverity(s)}
                    className={cn("px-2.5 py-1 rounded font-bold uppercase transition-opacity", st.badge, !active && "opacity-30")}
                  >
                    {st.label}
                  </button>
                );
              })}
            </div>

            <HitBucket
              title="Contraindications"
              icon={<ShieldAlert className="h-4 w-4" />}
              hits={filterHits(result.contraindications)}
              emptyText="No contraindications found for the given inputs."
            />
            <HitBucket
              title="Drug interactions"
              icon={<Atom className="h-4 w-4" />}
              hits={filterHits(result.interactions)}
              emptyText="No drug-drug interactions found."
              showPair
            />
            <HitBucket
              title="Adverse effects"
              icon={<Activity className="h-4 w-4" />}
              hits={filterHits(result.adverse_effects)}
              emptyText="No adverse effects listed."
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty state */}
      {!result && drugs.length === 0 && (
        <div className="text-center py-16">
          <div className="h-20 w-20 mx-auto rounded-3xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center mb-5">
            <Stethoscope className="h-10 w-10 text-primary" />
          </div>
          <h3 className="text-2xl font-bold mb-2 gradient-text">Clinical co-administration check</h3>
          <p className="text-muted-foreground max-w-lg mx-auto leading-relaxed">
            Add one or more active substances and, optionally, patient conditions (pregnancy,
            renal or hepatic impairment, G6PD deficiency, and more). Get contraindications,
            drug-drug interactions, and adverse effects — each severity-graded, sourced from
            openFDA labels and DrugBank.
          </p>
        </div>
      )}
    </div>
  );
}

function HitBucket({
  title, icon, hits, emptyText, showPair = false,
}: {
  title: string;
  icon: React.ReactNode;
  hits: CoAdminHit[];
  emptyText: string;
  showPair?: boolean;
}) {
  return (
    <Card className="glass-card border-border overflow-hidden">
      <CardHeader className="pb-4">
        <CardTitle className="text-lg flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center text-primary">{icon}</div>
          <span className="text-foreground">{title}</span>
          <span className="text-sm text-muted-foreground">({hits.length})</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {hits.length === 0 ? (
          <div className="p-4 rounded-lg bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
            <p className="text-sm text-green-800 dark:text-green-300">{emptyText}</p>
          </div>
        ) : (
          hits.map((hit, i) => {
            const st = severityStyles(hit.severity);
            return (
              <div key={i} className={cn("p-4 rounded-lg border", st.card)}>
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className={cn("px-2 py-0.5 rounded text-xs font-bold uppercase", st.badge)}>{st.label}</span>
                  <span className="text-muted-foreground">•</span>
                  <span className={cn("font-semibold text-sm", st.text)}>
                    {showPair ? hit.drugs.join(" ↔ ") : hit.drugs.join(", ")}
                  </span>
                  {hit.condition_label && !showPair && (
                    <>
                      <span className="text-muted-foreground text-xs">—</span>
                      <span className="text-xs text-muted-foreground">{hit.condition_label}</span>
                    </>
                  )}
                </div>
                <p className={cn("text-sm leading-relaxed", st.text)}>{hit.description}</p>
                {hit.source && <p className="text-[11px] text-muted-foreground mt-2">{hit.source}</p>}
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
