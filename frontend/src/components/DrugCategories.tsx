import { useState, useEffect } from "react";
import { ChevronRight, Pill, Search, Loader2, ServerCrash, X, AlertTriangle, CheckCircle, ArrowRight } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { waitForApiCheck } from "@/lib/drugData";
import * as api from "@/lib/api";
import { cn } from "@/lib/utils";

interface CategoryInfo {
  name: string;
  count: number;
}

interface DrugInfo {
  name: string;
  type: string | null;
  interactionCount: number;
}

interface SelectedDrugForCheck {
  name: string;
  category: string;
}

interface InteractionResult {
  compatible: boolean;
  issues: string[];
  warnings: string[];
  recommendations: string[];
  interactions: Array<{
    drug: string;
    description: string;
    severity: string;
  }>;
  dosing?: {
    drug1: { frequency?: string; times_per_day?: string };
    drug2: { frequency?: string; times_per_day?: string };
  };
  routes?: {
    drug1: string[];
    drug2: string[];
    common: string[];
  };
}

interface AlternativeDrug {
  name: string;
  type: string | null;
  has_dosing: boolean;
  frequency: string | null;
  routes: string[];
}

export function DrugCategories() {
  const [searchQuery, setSearchQuery] = useState("");
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [categoryDrugs, setCategoryDrugs] = useState<DrugInfo[]>([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(true);
  const [isLoadingDrugs, setIsLoadingDrugs] = useState(false);
  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Drug selection for compatibility check
  const [drug1, setDrug1] = useState<SelectedDrugForCheck | null>(null);
  const [drug2, setDrug2] = useState<SelectedDrugForCheck | null>(null);
  const [selectingFor, setSelectingFor] = useState<1 | 2 | null>(null);
  const [isCheckingCompatibility, setIsCheckingCompatibility] = useState(false);
  const [compatibilityResult, setCompatibilityResult] = useState<InteractionResult | null>(null);
  
  // Alternatives when interactions are found
  const [alternativesForDrug1, setAlternativesForDrug1] = useState<AlternativeDrug[]>([]);
  const [alternativesForDrug2, setAlternativesForDrug2] = useState<AlternativeDrug[]>([]);
  const [isLoadingAlternatives, setIsLoadingAlternatives] = useState(false);

  // Check API and load categories on mount - FAST: just load names, no counts
  useEffect(() => {
    async function loadCategories() {
      const apiAvailable = await waitForApiCheck();
      setApiReady(apiAvailable);
      
      if (!apiAvailable) {
        setIsLoadingCategories(false);
        return;
      }

      try {
        const categoryNames = await api.getCategories();
        // Just set names immediately - no counts to speed up loading
        const categoryInfos: CategoryInfo[] = categoryNames.map(name => ({ 
          name, 
          count: -1 // -1 means "not loaded yet"
        }));
        setCategories(categoryInfos);
      } catch (err) {
        console.error("Failed to load categories:", err);
        setError("Failed to load categories from backend");
      } finally {
        setIsLoadingCategories(false);
      }
    }
    
    loadCategories();
  }, []);

  const filteredCategories = categories.filter((cat) =>
    cat.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCategorySelect = async (category: string) => {
    setSelectedCategory(category);
    setIsLoadingDrugs(true);
    setError(null);
    
    try {
      const drugNames = await api.getDrugsByCategory(category);
      
      // Just show names immediately - no individual API calls for speed
      const drugsWithInfo: DrugInfo[] = drugNames.map(name => ({
        name,
        type: null,
        interactionCount: 0,
      }));
      
      setCategoryDrugs(drugsWithInfo);
    } catch (err) {
      console.error("Failed to load drugs for category:", err);
      setError("Failed to load drugs for this category");
      setCategoryDrugs([]);
    } finally {
      setIsLoadingDrugs(false);
    }
  };

  const handleDrugSelect = (drugName: string) => {
    if (selectingFor === 1) {
      setDrug1({ name: drugName, category: selectedCategory || '' });
      setSelectingFor(null);
      setSelectedCategory(null);
      setCategoryDrugs([]);
    } else if (selectingFor === 2) {
      setDrug2({ name: drugName, category: selectedCategory || '' });
      setSelectingFor(null);
      setSelectedCategory(null);
      setCategoryDrugs([]);
    }
  };

  const startSelectingDrug = (drugNumber: 1 | 2) => {
    setSelectingFor(drugNumber);
    setSelectedCategory(null);
    setCategoryDrugs([]);
    setCompatibilityResult(null);
  };

  const clearDrug = (drugNumber: 1 | 2) => {
    if (drugNumber === 1) {
      setDrug1(null);
    } else {
      setDrug2(null);
    }
    setCompatibilityResult(null);
    setAlternativesForDrug1([]);
    setAlternativesForDrug2([]);
  };

  const checkCompatibility = async () => {
    if (!drug1 || !drug2) return;
    
    setIsCheckingCompatibility(true);
    setError(null);
    setAlternativesForDrug1([]);
    setAlternativesForDrug2([]);
    
    try {
      const result = await api.checkCompatibility(drug1.name, drug2.name);
      setCompatibilityResult({
        compatible: result.compatible,
        issues: result.issues,
        warnings: result.warnings,
        recommendations: result.recommendations,
        interactions: result.interactions,
      });
      
      // If there are interactions, find compatible alternatives
      if (result.interactions.length > 0 || result.warnings.length > 0) {
        setIsLoadingAlternatives(true);
        try {
          // Find alternatives from Drug2's category that don't interact with Drug1
          // AND alternatives from Drug1's category that don't interact with Drug2
          const [altForDrug1, altForDrug2] = await Promise.all([
            api.findCompatibleAlternatives(drug1.name, drug2.category, 5),
            api.findCompatibleAlternatives(drug2.name, drug1.category, 5)
          ]);
          
          setAlternativesForDrug1(altForDrug1.alternatives);
          setAlternativesForDrug2(altForDrug2.alternatives);
        } catch (altErr) {
          console.error("Failed to find alternatives:", altErr);
          // Don't show error - alternatives are optional
        } finally {
          setIsLoadingAlternatives(false);
        }
      }
    } catch (err) {
      console.error("Failed to check compatibility:", err);
      setError("Failed to check drug compatibility");
    } finally {
      setIsCheckingCompatibility(false);
    }
  };

  const cancelSelection = () => {
    setSelectingFor(null);
    setSelectedCategory(null);
    setCategoryDrugs([]);
  };

  return (
    <div className="space-y-6">
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

      {/* Error Display */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-xl bg-warning/10 border border-warning/30 text-warning text-sm"
        >
          {error}
        </motion.div>
      )}

      {/* Drug Selection Panel for Compatibility Check */}
      <Card className="glass-card border-2 border-primary/20">
        <CardContent className="p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-primary/20 flex items-center justify-center">
              ⚗️
            </div>
            Check Drug Interactions
          </h3>
          
          <div className="flex flex-col md:flex-row items-center gap-4">
            {/* Drug 1 Selection */}
            <div className="flex-1 w-full">
              {drug1 ? (
                <div className="p-4 rounded-xl bg-primary/10 border border-primary/30 flex items-center justify-between">
                  <div>
                    <p className="font-medium">{drug1.name}</p>
                    <p className="text-xs text-muted-foreground">{drug1.category}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => clearDrug(1)}
                    className="h-8 w-8 p-0"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  className={cn(
                    "w-full h-16 border-dashed text-left justify-start",
                    selectingFor === 1 && "border-primary bg-primary/5"
                  )}
                  onClick={() => startSelectingDrug(1)}
                >
                  <Pill className="h-5 w-5 mr-3 text-muted-foreground" />
                  <span className="text-muted-foreground">
                    {selectingFor === 1 ? "Select from categories below..." : "Select First Drug"}
                  </span>
                </Button>
              )}
            </div>

            {/* Arrow */}
            <div className="hidden md:flex items-center justify-center">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center">
                <ArrowRight className="h-5 w-5 text-muted-foreground" />
              </div>
            </div>

            {/* Drug 2 Selection */}
            <div className="flex-1 w-full">
              {drug2 ? (
                <div className="p-4 rounded-xl bg-accent/10 border border-accent/30 flex items-center justify-between">
                  <div>
                    <p className="font-medium">{drug2.name}</p>
                    <p className="text-xs text-muted-foreground">{drug2.category}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => clearDrug(2)}
                    className="h-8 w-8 p-0"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  className={cn(
                    "w-full h-16 border-dashed text-left justify-start",
                    selectingFor === 2 && "border-accent bg-accent/5"
                  )}
                  onClick={() => startSelectingDrug(2)}
                >
                  <Pill className="h-5 w-5 mr-3 text-muted-foreground" />
                  <span className="text-muted-foreground">
                    {selectingFor === 2 ? "Select from categories below..." : "Select Second Drug"}
                  </span>
                </Button>
              )}
            </div>

            {/* Check Button */}
            <Button
              onClick={checkCompatibility}
              disabled={!drug1 || !drug2 || isCheckingCompatibility}
              className="h-16 px-8 bg-gradient-to-r from-primary to-accent hover:opacity-90"
            >
              {isCheckingCompatibility ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <>
                  <span>Check Interactions</span>
                </>
              )}
            </Button>
          </div>

          {/* Cancel Selection Button */}
          {selectingFor && (
            <div className="mt-4 text-center">
              <Button variant="ghost" size="sm" onClick={cancelSelection}>
                Cancel Selection
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Compatibility Results */}
      <AnimatePresence>
        {compatibilityResult && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
          >
            <Card className={cn(
              "glass-card border-2",
              compatibilityResult.compatible 
                ? "border-success/30 bg-success/5" 
                : "border-border bg-card"
            )}>
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    {compatibilityResult.compatible ? (
                      <CheckCircle className="h-8 w-8 text-success" />
                    ) : (
                      <AlertTriangle className="h-8 w-8 text-muted-foreground" />
                    )}
                    <div>
                      <h3 className="text-xl font-bold">
                        {compatibilityResult.compatible ? "Compatible" : "Results"}
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        {drug1?.name} + {drug2?.name}
                      </p>
                      {/* Dosing Frequency Display */}
                      {(compatibilityResult.dosing?.drug1?.frequency || compatibilityResult.dosing?.drug2?.frequency) && (
                        <div className="flex flex-wrap gap-3 mt-2 text-xs">
                          {compatibilityResult.dosing?.drug1?.frequency && (
                            <span className="px-2 py-0.5 rounded bg-primary/10 text-primary">
                              {drug1?.name}: {compatibilityResult.dosing.drug1.frequency}
                              {compatibilityResult.dosing.drug1.times_per_day && ` (${compatibilityResult.dosing.drug1.times_per_day}x/day)`}
                            </span>
                          )}
                          {compatibilityResult.dosing?.drug2?.frequency && (
                            <span className="px-2 py-0.5 rounded bg-primary/10 text-primary">
                              {drug2?.name}: {compatibilityResult.dosing.drug2.frequency}
                              {compatibilityResult.dosing.drug2.times_per_day && ` (${compatibilityResult.dosing.drug2.times_per_day}x/day)`}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setDrug1(null);
                      setDrug2(null);
                      setCompatibilityResult(null);
                      setAlternativesForDrug1([]);
                      setAlternativesForDrug2([]);
                    }}
                    className="flex items-center gap-2"
                  >
                    <ArrowRight className="h-4 w-4 rotate-180" />
                    Start Over
                  </Button>
                </div>

                {/* Issues (compatibility/3D printing etc. - neutral, not interaction severity) */}
                {compatibilityResult.issues.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-medium text-foreground mb-2">⚠️ Issues</h4>
                    <ul className="space-y-1">
                      {compatibilityResult.issues.map((issue, i) => (
                        <li key={i} className="text-sm bg-muted/50 border border-border p-2 rounded-lg text-foreground">
                          {issue}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Warnings */}
                {compatibilityResult.warnings.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-medium text-warning mb-2">⚡ Warnings</h4>
                    <ul className="space-y-1">
                      {compatibilityResult.warnings.map((warning, i) => (
                        <li key={i} className="text-sm bg-warning/10 p-2 rounded-lg">
                          {warning}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Interactions */}
                {compatibilityResult.interactions.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-medium mb-2">📋 Detailed Interactions</h4>
                    
                    {/* Severity Legend */}
                    <div className="flex flex-wrap gap-3 mb-3 text-xs">
                      <span className="px-2 py-1 rounded bg-red-500 text-white font-bold">🔴 SEVERE</span>
                      <span className="px-2 py-1 rounded bg-amber-500 text-white font-bold">🟡 MODERATE</span>
                      <span className="px-2 py-1 rounded bg-green-500 text-white font-bold">🟢 MINOR</span>
                    </div>

                    <ScrollArea className="h-[200px]">
                      <div className="space-y-2 pr-4">
                        {compatibilityResult.interactions.map((interaction, i) => (
                          <div 
                            key={i} 
                            className={`p-3 rounded-lg border ${
                              interaction.severity === 'severe' 
                                ? 'bg-red-500/10 border-red-500/30' 
                                : interaction.severity === 'moderate' 
                                ? 'bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-800/50' 
                                : interaction.severity === 'minor'
                                ? 'bg-green-500/10 border-green-500/30'
                                : 'bg-muted/50 border-border'
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-medium text-sm">{interaction.drug}</span>
                              <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${
                                interaction.severity === 'severe' 
                                  ? 'bg-red-500 text-white' 
                                  : interaction.severity === 'moderate' 
                                  ? 'bg-amber-500 text-white' 
                                  : interaction.severity === 'minor'
                                  ? 'bg-green-500 text-white'
                                  : 'bg-muted text-muted-foreground'
                              }`}>
                                {interaction.severity === 'severe' ? '🔴' : interaction.severity === 'moderate' ? '🟡' : interaction.severity === 'minor' ? '🟢' : '⚪'} {interaction.severity}
                              </span>
                            </div>
                            <p className="text-sm text-muted-foreground">{interaction.description}</p>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </div>
                )}

                {/* Recommendations */}
                {compatibilityResult.recommendations.length > 0 && (
                  <div>
                    <h4 className="font-medium text-primary mb-2">💡 Recommendations</h4>
                    <ul className="space-y-1">
                      {compatibilityResult.recommendations.map((rec, i) => (
                        <li key={i} className="text-sm bg-primary/10 p-2 rounded-lg">
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* No interactions message */}
                {compatibilityResult.compatible && 
                 compatibilityResult.interactions.length === 0 && 
                 compatibilityResult.warnings.length === 0 && (
                  <p className="text-success text-sm">
                    No known interactions found between these drugs.
                  </p>
                )}

                {/* Quick Actions */}
                <div className="mt-4 pt-4 border-t border-border flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setDrug1(null);
                      setCompatibilityResult(null);
                      setAlternativesForDrug1([]);
                      setAlternativesForDrug2([]);
                      startSelectingDrug(1);
                    }}
                  >
                    🔄 Change {drug1?.name?.slice(0, 15)}...
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setDrug2(null);
                      setCompatibilityResult(null);
                      setAlternativesForDrug1([]);
                      setAlternativesForDrug2([]);
                      startSelectingDrug(2);
                    }}
                  >
                    🔄 Change {drug2?.name?.slice(0, 15)}...
                  </Button>
                </div>

                {/* Compatible Alternatives Section */}
                {(alternativesForDrug1.length > 0 || alternativesForDrug2.length > 0 || isLoadingAlternatives) && (
                  <div className="mt-6 pt-6 border-t border-border">
                    <h4 className="font-semibold text-lg mb-4 flex items-center gap-2">
                      <span className="text-xl">💡</span>
                      Compatible Alternatives
                    </h4>
                    
                    {isLoadingAlternatives ? (
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Finding compatible alternatives...</span>
                      </div>
                    ) : (
                      <div className="grid md:grid-cols-2 gap-4">
                        {/* Alternatives to replace Drug2 (compatible with Drug1) */}
                        {alternativesForDrug1.length > 0 && (
                          <div className="p-4 rounded-xl bg-success/5 border border-success/20">
                            <p className="text-sm font-medium mb-3">
                              🔄 Replace <span className="text-destructive">{drug2?.name}</span> with:
                            </p>
                            <p className="text-xs text-muted-foreground mb-2">
                              (From {drug2?.category}, compatible with {drug1?.name})
                            </p>
                            <div className="space-y-2">
                              {alternativesForDrug1.map((alt, i) => (
                                <div 
                                  key={i}
                                  className="p-2 rounded-lg bg-background/50 border flex items-center justify-between"
                                >
                                  <div>
                                    <span className="font-medium text-sm text-success">{alt.name}</span>
                                    {alt.frequency && (
                                      <span className="text-xs text-muted-foreground ml-2">
                                        ({alt.frequency})
                                      </span>
                                    )}
                                  </div>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 text-xs"
                                    onClick={() => {
                                      setDrug2({ name: alt.name, category: drug2?.category || '' });
                                      setCompatibilityResult(null);
                                      setAlternativesForDrug1([]);
                                      setAlternativesForDrug2([]);
                                    }}
                                  >
                                    Use This
                                  </Button>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Alternatives to replace Drug1 (compatible with Drug2) */}
                        {alternativesForDrug2.length > 0 && (
                          <div className="p-4 rounded-xl bg-info/5 border border-info/20">
                            <p className="text-sm font-medium mb-3">
                              🔄 Replace <span className="text-destructive">{drug1?.name}</span> with:
                            </p>
                            <p className="text-xs text-muted-foreground mb-2">
                              (From {drug1?.category}, compatible with {drug2?.name})
                            </p>
                            <div className="space-y-2">
                              {alternativesForDrug2.map((alt, i) => (
                                <div 
                                  key={i}
                                  className="p-2 rounded-lg bg-background/50 border flex items-center justify-between"
                                >
                                  <div>
                                    <span className="font-medium text-sm text-info">{alt.name}</span>
                                    {alt.frequency && (
                                      <span className="text-xs text-muted-foreground ml-2">
                                        ({alt.frequency})
                                      </span>
                                    )}
                                  </div>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 text-xs"
                                    onClick={() => {
                                      setDrug1({ name: alt.name, category: drug1?.category || '' });
                                      setCompatibilityResult(null);
                                      setAlternativesForDrug1([]);
                                      setAlternativesForDrug2([]);
                                    }}
                                  >
                                    Use This
                                  </Button>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {alternativesForDrug1.length === 0 && alternativesForDrug2.length === 0 && !isLoadingAlternatives && (
                          <div className="col-span-2 text-center text-muted-foreground text-sm py-4">
                            No compatible alternatives found in these categories.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search categories..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10 h-12"
        />
      </div>

      {/* Breadcrumb */}
      {selectedCategory && (
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={() => {
              setSelectedCategory(null);
              setCategoryDrugs([]);
            }}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            Categories
          </button>
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
          <span className="text-foreground font-medium">{selectedCategory}</span>
          {selectingFor && (
            <Badge variant="outline" className="ml-2">
              Selecting Drug {selectingFor}
            </Badge>
          )}
        </div>
      )}

      {/* Loading Categories */}
      {isLoadingCategories && (
        <div className="flex items-center justify-center py-20">
          <div className="text-center">
            <Loader2 className="h-12 w-12 text-primary mx-auto animate-spin mb-4" />
            <p className="text-muted-foreground">Loading categories from database...</p>
          </div>
        </div>
      )}

      <AnimatePresence mode="wait">
        {/* Categories Grid with Scroll */}
        {!selectedCategory && !isLoadingCategories && (
          <motion.div
            key="categories"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
          >
            <ScrollArea className="h-[500px]">
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 pr-4">
                {filteredCategories.map((category, index) => (
                <motion.button
                    key={category.name}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: Math.min(index * 0.01, 0.5) }}
                    onClick={() => handleCategorySelect(category.name)}
                  className="group text-left"
                >
                    <Card className={cn(
                      "glass-card h-full transition-all duration-300 hover:scale-[1.02] hover:shadow-lg",
                      selectingFor && "border-2 border-dashed border-primary/50"
                    )}>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between mb-2">
                        <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                          <Pill className="h-5 w-5 text-primary" />
                        </div>
                      </div>
                      <h3 className="font-medium text-sm leading-tight">
                          {category.name}
                      </h3>
                    </CardContent>
                  </Card>
                </motion.button>
                ))}
                {filteredCategories.length === 0 && !isLoadingCategories && apiReady && (
                  <div className="col-span-full text-center py-12 text-muted-foreground">
                    No categories found matching "{searchQuery}"
                  </div>
                )}
              </div>
            </ScrollArea>
          </motion.div>
        )}

        {/* Loading Drugs */}
        {selectedCategory && isLoadingDrugs && (
          <motion.div
            key="loading-drugs"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center justify-center py-20"
          >
            <div className="text-center">
              <Loader2 className="h-12 w-12 text-primary mx-auto animate-spin mb-4" />
              <p className="text-muted-foreground">Loading drugs in {selectedCategory}...</p>
            </div>
          </motion.div>
        )}

        {/* Drugs List */}
        {selectedCategory && !isLoadingDrugs && (
          <motion.div
            key="drugs"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
          >
            <ScrollArea className="h-[500px]">
              <div className="space-y-2 pr-4">
                {categoryDrugs.length > 0 ? (
                  categoryDrugs.map((drug, index) => (
                    <motion.button
                      key={drug.name}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: Math.min(index * 0.02, 0.5) }}
                      onClick={() => handleDrugSelect(drug.name)}
                      className="w-full text-left"
                    >
                      <Card className={cn(
                        "glass-card transition-all duration-200 hover:bg-muted/50",
                        selectingFor === 1 && "hover:border-primary hover:bg-primary/5",
                        selectingFor === 2 && "hover:border-accent hover:bg-accent/5"
                      )}>
                        <CardContent className="p-4 flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className={cn(
                              "h-10 w-10 rounded-lg flex items-center justify-center",
                              selectingFor === 1 ? "bg-primary/20" : 
                              selectingFor === 2 ? "bg-accent/20" : "bg-primary/10"
                            )}>
                              <Pill className={cn(
                                "h-5 w-5",
                                selectingFor === 1 ? "text-primary" : 
                                selectingFor === 2 ? "text-accent" : "text-primary"
                              )} />
                            </div>
                            <div>
                              <h4 className="font-medium">{drug.name}</h4>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {selectingFor && (
                              <Badge variant={selectingFor === 1 ? "default" : "secondary"}>
                                Select as Drug {selectingFor}
                              </Badge>
                            )}
                          <ChevronRight className="h-5 w-5 text-muted-foreground" />
                          </div>
                        </CardContent>
                      </Card>
                    </motion.button>
                  ))
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    No drugs found in this category
                  </div>
                )}
              </div>
            </ScrollArea>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
