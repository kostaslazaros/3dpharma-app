import { useState, useEffect } from "react";
import { Search, Plus, X, CheckCircle2, XCircle, AlertTriangle, Pill, Beaker, Atom, Zap, Shield, Loader2, ServerCrash } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { searchDrugsAsync, checkMultiDrugCompatibilityAsync, waitForApiCheck, type Drug, type MultiDrugCompatibilityResult } from "@/lib/drugData";
import { cn } from "@/lib/utils";

interface DrugSlot {
  id: number;
  query: string;
  drug: Drug | null;
  results: Drug[];
  isSearching: boolean;
}

const gradientColors = [
  "from-primary to-info",
  "from-accent to-success",
  "from-warning to-destructive",
  "from-info to-primary",
  "from-success to-accent",
];

export function CompatibilityCheck() {
  const [drugSlots, setDrugSlots] = useState<DrugSlot[]>([
    { id: 1, query: "", drug: null, results: [], isSearching: false },
    { id: 2, query: "", drug: null, results: [], isSearching: false },
  ]);
  const [result, setResult] = useState<MultiDrugCompatibilityResult | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [nextId, setNextId] = useState(3);
  const [apiReady, setApiReady] = useState<boolean | null>(null);

  // Check API status on mount
  useEffect(() => {
    waitForApiCheck().then((available) => {
      setApiReady(available);
    });
  }, []);

  const handleSearch = async (slotId: number, value: string) => {
    // Update query immediately
    setDrugSlots(slots =>
      slots.map(slot =>
        slot.id === slotId
          ? { ...slot, query: value, isSearching: value.length >= 2 }
          : slot
      )
    );

    if (value.length >= 2) {
      try {
        const results = await searchDrugsAsync(value);
        setDrugSlots(slots =>
          slots.map(slot =>
            slot.id === slotId
              ? { ...slot, results, isSearching: false }
              : slot
          )
        );
      } catch (error) {
        console.error("Search error:", error);
        setDrugSlots(slots =>
          slots.map(slot =>
            slot.id === slotId
              ? { ...slot, results: [], isSearching: false }
              : slot
          )
        );
      }
    } else {
      setDrugSlots(slots =>
        slots.map(slot =>
          slot.id === slotId
            ? { ...slot, results: [], isSearching: false }
            : slot
        )
      );
    }
  };

  const selectDrug = (slotId: number, drug: Drug) => {
    setDrugSlots(slots =>
      slots.map(slot =>
        slot.id === slotId
          ? { ...slot, drug, query: drug.name, results: [], isSearching: false }
          : slot
      )
    );
    setResult(null);
  };

  const removeDrug = (slotId: number) => {
    setDrugSlots(slots =>
      slots.map(slot =>
        slot.id === slotId
          ? { ...slot, drug: null, query: "", results: [], isSearching: false }
          : slot
      )
    );
    setResult(null);
  };

  const addDrugSlot = () => {
    if (drugSlots.length < 5) {
      setDrugSlots([...drugSlots, { id: nextId, query: "", drug: null, results: [], isSearching: false }]);
      setNextId(nextId + 1);
    }
  };

  const removeDrugSlot = (slotId: number) => {
    if (drugSlots.length > 2) {
      setDrugSlots(slots => slots.filter(slot => slot.id !== slotId));
      setResult(null);
    }
  };

  const handleCheck = async () => {
    const selectedDrugs = drugSlots.filter(slot => slot.drug).map(slot => slot.drug!.name);
    if (selectedDrugs.length >= 2) {
      setIsChecking(true);
      try {
        const compatResult = await checkMultiDrugCompatibilityAsync(selectedDrugs);
        setResult(compatResult);
      } catch (error) {
        console.error("Compatibility check error:", error);
        // Show error in result
        setResult({
          drugs: selectedDrugs,
          compatible: false,
          issues: [`Error checking compatibility: ${error instanceof Error ? error.message : 'Unknown error'}`],
          warnings: [],
          recommendations: [],
          interactions: [],
          drugDetails: [],
          commonRoutes: [],
        });
      } finally {
        setIsChecking(false);
      }
    }
  };

  const resetCheck = () => {
    setDrugSlots([
      { id: nextId, query: "", drug: null, results: [], isSearching: false },
      { id: nextId + 1, query: "", drug: null, results: [], isSearching: false },
    ]);
    setNextId(nextId + 2);
    setResult(null);
  };

  const selectedCount = drugSlots.filter(slot => slot.drug).length;

  return (
    <div className="space-y-8">
      {/* API Status Warning */}
      {apiReady === false && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-xl bg-destructive/10 border border-destructive/30 flex items-center gap-4"
        >
          <ServerCrash className="h-8 w-8 text-destructive flex-shrink-0" />
          <div>
            <p className="font-semibold text-destructive">Backend API Not Available</p>
            <p className="text-sm text-muted-foreground">
              Please ensure the FastAPI server is running on http://localhost:8000
            </p>
          </div>
        </motion.div>
      )}

      {/* Drug Selection Grid */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="space-y-4"
      >
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-muted-foreground">
            Select {drugSlots.length} compounds to analyze ({selectedCount} selected)
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={addDrugSlot}
            disabled={drugSlots.length >= 5}
            className="gap-2"
          >
            <Plus className="h-4 w-4" />
            Add Compound
          </Button>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {drugSlots.map((slot, index) => (
            <motion.div
              key={slot.id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative"
            >
              <div className="flex items-center gap-2 mb-3">
                <div className={cn(
                  "h-6 w-6 rounded-lg flex items-center justify-center",
                  slot.drug 
                    ? `bg-gradient-to-br ${gradientColors[index % gradientColors.length]} text-white` 
                    : "bg-muted"
                )}>
                  <span className="text-xs font-mono">{String(index + 1).padStart(2, '0')}</span>
                </div>
                <label className="text-sm font-semibold text-muted-foreground flex-1">
                  Compound {index + 1}
                </label>
                {drugSlots.length > 2 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeDrugSlot(slot.id)}
                    className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>

              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                {slot.isSearching && (
                  <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground animate-spin" />
                )}
                <Input
                  placeholder="Search compound..."
                  value={slot.query}
                  onChange={(e) => handleSearch(slot.id, e.target.value)}
                  className={cn(
                    "pl-11 h-12 bg-card/80 backdrop-blur-sm border-border/50 rounded-xl",
                    slot.drug && `border-primary/50 bg-gradient-to-r ${gradientColors[index % gradientColors.length].replace('from-', 'from-').replace(' to-', '/5 to-')}/5`
                  )}
                />
              </div>

              {slot.drug && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className={cn(
                    "mt-3 p-3 rounded-xl border",
                    `bg-gradient-to-br ${gradientColors[index % gradientColors.length].replace('from-', 'from-').replace(' to-', '/10 to-')}/5 border-primary/20`
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "h-8 w-8 rounded-lg flex items-center justify-center",
                      `bg-gradient-to-br ${gradientColors[index % gradientColors.length]}`
                    )}>
                      <Pill className="h-4 w-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className="font-semibold text-sm truncate block">{slot.drug.name}</span>
                      <p className="text-xs text-muted-foreground truncate">
                        {slot.drug.categories.slice(0, 2).join(" • ")}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeDrug(slot.id)}
                      className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive shrink-0"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </motion.div>
              )}

              <AnimatePresence>
                {slot.results.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="absolute top-full left-0 right-0 mt-2 z-50 glass-card rounded-xl overflow-hidden"
                  >
                    {slot.results.slice(0, 5).map((drug) => (
                      <button
                        key={drug.id}
                        onClick={() => selectDrug(slot.id, drug)}
                        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-primary/5 transition-colors text-left text-sm border-b border-border/30 last:border-0"
                      >
                        <Pill className="h-4 w-4 text-primary" />
                        <span className="font-medium">{drug.name}</span>
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Action Buttons */}
      <motion.div
        className="flex gap-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
      >
        <Button
          onClick={handleCheck}
          disabled={selectedCount < 2 || isChecking}
          className="flex-1 h-14 text-base font-semibold bg-gradient-to-r from-primary to-accent hover:opacity-90 transition-opacity btn-shine rounded-xl"
        >
          {isChecking ? (
            <>
              <Loader2 className="h-5 w-5 mr-2 animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Atom className="h-5 w-5 mr-2 animate-spin-slow" />
              Analyze {selectedCount} Compounds
            </>
          )}
        </Button>
        <Button
          variant="outline"
          onClick={resetCheck}
          disabled={isChecking}
          className="h-14 px-6 rounded-xl border-border/50"
        >
          Reset
        </Button>
      </motion.div>

      {/* Results */}
      <AnimatePresence mode="wait">
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }}
            className="space-y-6"
          >
            {/* Compatibility Status */}
            <Card className="glass-card border-border overflow-hidden">
              <div className="p-6 flex items-center gap-4">
                <div className={cn(
                  "h-12 w-12 rounded-xl flex items-center justify-center",
                  result.compatible
                    ? "bg-primary/10"
                    : "bg-muted"
                )}>
                  {result.compatible ? (
                    <CheckCircle2 className="h-6 w-6 text-primary" />
                  ) : (
                    <XCircle className="h-6 w-6 text-muted-foreground" />
                  )}
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-foreground">
                    {result.compatible ? "Compatible for 3D Printing" : "Results"}
                  </h3>
                  <p className="text-muted-foreground mt-1 flex items-center gap-2 flex-wrap">
                    {result.drugs.map((drug, i) => (
                      <span key={drug} className="flex items-center gap-1">
                        <span className="font-semibold text-foreground">{drug}</span>
                        {i < result.drugs.length - 1 && <span className="text-muted-foreground">+</span>}
                      </span>
                    ))}
                  </p>
                </div>
              </div>
            </Card>

            {/* Recommendations */}
            {result.recommendations.length > 0 && (
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 }}
              >
                <Card className="glass-card border-border overflow-hidden">
                  <CardHeader className="pb-4">
                    <CardTitle className="flex items-center gap-3 text-lg">
                      <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
                        <Zap className="h-4 w-4 text-primary" />
                      </div>
                      <span className="text-foreground">Recommendations</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {result.recommendations.map((rec, i) => (
                      <div
                        key={i}
                        className="p-3 rounded-lg bg-muted/50 border border-border text-sm text-muted-foreground flex items-start gap-3"
                      >
                        <CheckCircle2 className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                        <span>{rec}</span>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Interactions Detail */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
            >
              <Card className={cn(
                "glass-card overflow-hidden",
                result.interactions.length === 0
                  ? "border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-950/20"
                  : "border-border"
              )}>
                <CardHeader className="pb-4">
                  <CardTitle className="text-lg flex items-center gap-3">
                    <div className={cn(
                      "h-8 w-8 rounded-lg flex items-center justify-center",
                      result.interactions.length === 0
                        ? "bg-green-100 dark:bg-green-900/50"
                        : "bg-muted"
                    )}>
                      <Atom className={cn(
                        "h-4 w-4",
                        result.interactions.length === 0 ? "text-green-600 dark:text-green-400" : "text-primary"
                      )} />
                    </div>
                    <span className="text-foreground">Interaction Analysis</span>
                    {result.interactions.length === 0 ? (
                      <span className="text-sm font-medium text-green-700 dark:text-green-400">No interactions</span>
                    ) : (
                      <span className="text-sm text-muted-foreground">({result.interactions.length})</span>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Severity Legend - only when there are interactions */}
                  {result.interactions.length > 0 && (
                    <div className="flex flex-wrap gap-3 text-xs mb-4">
                      <span className="px-2 py-1 rounded bg-red-500 text-white font-bold">SEVERE</span>
                      <span className="px-2 py-1 rounded bg-amber-500 text-white font-bold">MODERATE</span>
                      <span className="px-2 py-1 rounded bg-green-500 text-white font-bold">MINOR</span>
                    </div>
                  )}

                  {result.interactions.length > 0 ? (
                    result.interactions.map((item, i) => (
                      <div
                        key={i}
                        className={cn(
                          "p-4 rounded-lg border",
                          item.interaction.severity === 'severe'
                            ? "bg-red-50 border-red-200 dark:bg-red-950/30 dark:border-red-800"
                            : item.interaction.severity === 'moderate'
                            ? "bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-800/50"
                            : item.interaction.severity === 'minor'
                            ? "bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800"
                            : "bg-muted/30 border-border"
                        )}
                      >
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <span className={cn(
                            "px-2 py-0.5 rounded text-xs font-bold uppercase",
                            item.interaction.severity === 'severe' 
                              ? "bg-red-500 text-white"
                              : item.interaction.severity === 'moderate'
                              ? "bg-amber-500 text-white"
                              : item.interaction.severity === 'minor'
                              ? "bg-green-500 text-white"
                              : "bg-gray-400 text-white"
                          )}>
                            {item.interaction.severity}
                          </span>
                          <span className="text-muted-foreground">•</span>
                          <span className={cn(
                            "font-semibold text-sm",
                            item.interaction.severity === 'severe' 
                              ? "text-red-700 dark:text-red-400"
                              : item.interaction.severity === 'moderate'
                              ? "text-amber-800 dark:text-amber-300"
                              : item.interaction.severity === 'minor'
                              ? "text-green-700 dark:text-green-400"
                              : "text-foreground"
                          )}>{item.drug1}</span>
                          <span className="text-muted-foreground text-xs">↔</span>
                          <span className={cn(
                            "font-semibold text-sm",
                            item.interaction.severity === 'severe' 
                              ? "text-red-700 dark:text-red-400"
                              : item.interaction.severity === 'moderate'
                              ? "text-amber-800 dark:text-amber-300"
                              : item.interaction.severity === 'minor'
                              ? "text-green-700 dark:text-green-400"
                              : "text-foreground"
                          )}>{item.drug2}</span>
                        </div>
                        <p className={cn(
                          "text-sm leading-relaxed",
                          item.interaction.severity === 'severe' 
                            ? "text-red-800 dark:text-red-300"
                            : item.interaction.severity === 'moderate'
                            ? "text-amber-800 dark:text-amber-300"
                            : item.interaction.severity === 'minor'
                            ? "text-green-800 dark:text-green-300"
                            : "text-muted-foreground"
                        )}>
                          {item.interaction.description}
                        </p>
                      </div>
                    ))
                  ) : (
                    <div className="p-4 rounded-lg bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-center">
                      <CheckCircle2 className="h-6 w-6 text-green-600 dark:text-green-400 mx-auto mb-2" />
                      <p className="text-sm font-medium text-green-800 dark:text-green-300">No direct drug-drug interactions found</p>
                      <p className="text-xs text-green-700/80 dark:text-green-400/80 mt-1">
                        The selected compounds have no known interactions in our database
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>

            {/* Warnings - below Interaction Analysis */}
            {result.warnings.length > 0 && (
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.45 }}
              >
                <Card className="glass-card border-border overflow-hidden">
                  <CardHeader className="pb-4">
                    <CardTitle className="flex items-center gap-3 text-lg">
                      <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
                        <AlertTriangle className="h-4 w-4 text-amber-500" />
                      </div>
                      <span className="text-foreground">Warnings</span>
                      <span className="text-sm text-muted-foreground">({result.warnings.length})</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {result.warnings.map((warning, i) => (
                      <div
                        key={i}
                        className="p-3 rounded-lg bg-muted/50 border border-border text-sm text-foreground"
                      >
                        {warning}
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Drug Details Grid */}
            {result.drugDetails.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
              >
                <Card className="glass-card border-border h-full">
                  <CardHeader className="pb-4">
                    <CardTitle className="text-lg flex items-center gap-3">
                      <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
                        <Shield className="h-4 w-4 text-primary" />
                      </div>
                      <span className="text-foreground">Compound Details</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {result.drugDetails.map((drug, i) => (
                        <div
                          key={drug.name}
                          className="p-4 rounded-lg bg-muted/30 border border-border"
                        >
                          <div className="flex items-center gap-2 mb-3">
                            <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
                              <Pill className="h-3.5 w-3.5 text-primary" />
                            </div>
                            <span className="font-medium text-sm">{drug.name}</span>
                          </div>
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-muted-foreground text-xs">Frequency</span>
                              <span className="font-mono text-xs">{drug.frequency || 'N/A'}</span>
                            </div>
                            <div className="flex justify-between items-start">
                              <span className="text-muted-foreground text-xs">Routes</span>
                              <span className="text-xs text-right">
                                {drug.routes.length > 0 ? drug.routes.join(', ') : 'N/A'}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Common Routes */}
                    {result.commonRoutes.length > 0 && (
                      <div className="mt-4 p-3 rounded-lg bg-muted/30 border border-border">
                        <span className="text-xs text-muted-foreground block mb-2">Common Routes</span>
                        <div className="flex flex-wrap gap-2">
                          {result.commonRoutes.map((route) => (
                            <span key={route} className="text-xs px-2 py-1 rounded bg-primary/10 text-primary">
                              {route}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Critical Issues (compatibility/3D printing etc. - neutral, not interaction severity) */}
            {result.issues.length > 0 && (
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.5 }}
              >
                <Card className="glass-card border-border overflow-hidden">
                  <CardHeader className="pb-4">
                    <CardTitle className="flex items-center gap-3 text-lg text-foreground">
                      <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
                        <XCircle className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <span>Critical Issues</span>
                      <span className="text-sm text-muted-foreground">({result.issues.length})</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {result.issues.map((issue, i) => (
                      <div
                        key={i}
                        className="p-3 rounded-lg bg-muted/50 border border-border text-sm text-foreground"
                      >
                        {issue}
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty State */}
      {!result && selectedCount === 0 && (
        <motion.div
          className="text-center py-20"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          <div className="relative inline-block mb-6">
            <div className="h-24 w-24 rounded-3xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center">
              <Beaker className="h-12 w-12 text-primary" />
            </div>
            <div className="absolute inset-0 rounded-3xl bg-primary/10 blur-2xl -z-10" />
          </div>
          <h3 className="text-2xl font-bold mb-3 gradient-text">Analyze Multi-Drug Compatibility</h3>
          <p className="text-muted-foreground max-w-md mx-auto leading-relaxed">
            Select two or more compounds (up to 5) to check <strong className="text-foreground">drug-drug interactions</strong> and 
            evaluate their compatibility for 3D printing pharmaceutical formulations. 
            Get severity ratings, interaction details, and recommendations.
          </p>
        </motion.div>
      )}
    </div>
  );
}
