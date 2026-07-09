import { useState, useEffect } from "react";
import { Search, Pill, AlertCircle, Beaker, Clock, Activity, Sparkles, ChevronRight, ChevronDown, Loader2, ServerCrash, Tags } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { searchDrugsAsync, getDrugSummaryAsync, waitForApiCheck, isApiAvailable, type Drug } from "@/lib/drugData";

interface DrugInteraction {
  drugName: string;
  drugId: string;
  description: string;
  severity?: string;
}

interface DrugSummary {
  name: string;
  id: string;
  type: string;
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
  interactionCount: number;
  interactions: DrugInteraction[];
  properties: Record<string, string | undefined>;
  pharmacokinetics: Record<string, string | undefined>;
}

export function DrugSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Drug[]>([]);
  const [selectedDrug, setSelectedDrug] = useState<DrugSummary | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingDrug, setIsLoadingDrug] = useState(false);
  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [showCategories, setShowCategories] = useState(false);
  const [expandedPharmacokinetics, setExpandedPharmacokinetics] = useState<Set<string>>(new Set());
  const [showInteractions, setShowInteractions] = useState(false);
  const [showFoodInteractions, setShowFoodInteractions] = useState(false);
  const [interactionsLimit, setInteractionsLimit] = useState(50);

  // Check API status on mount
  useEffect(() => {
    waitForApiCheck().then((available) => {
      setApiReady(available);
    });
  }, []);

  const handleSearch = async (value: string) => {
    setQuery(value);
    setSearchError(null);
    if (value.length >= 2) {
      setIsSearching(true);
      try {
        const searchResults = await searchDrugsAsync(value);
        setResults(searchResults);
      } catch (error) {
        console.error("Search error:", error);
        setResults([]);
        setSearchError(error instanceof Error ? error.message : "Search failed");
      } finally {
        setIsSearching(false);
      }
    } else {
      setResults([]);
    }
  };

  const togglePharmacokinetics = (key: string) => {
    setExpandedPharmacokinetics(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleSelectDrug = async (drugName: string) => {
    setIsLoadingDrug(true);
    setQuery(drugName);
    setResults([]);
    setShowCategories(false);
    setExpandedPharmacokinetics(new Set());
    setShowInteractions(false);
    setShowFoodInteractions(false);
    setInteractionsLimit(50);
    
    try {
      const summary = await getDrugSummaryAsync(drugName);
      setSelectedDrug(summary);
    } catch (error) {
      console.error("Failed to get drug summary:", error);
      setSelectedDrug(null);
    } finally {
      setIsLoadingDrug(false);
    }
  };

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

      {/* Search Error Display */}
      {searchError && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-xl bg-warning/10 border border-warning/30 flex items-center gap-4"
        >
          <AlertCircle className="h-6 w-6 text-warning flex-shrink-0" />
          <p className="text-sm text-warning">{searchError}</p>
        </motion.div>
      )}

      {/* Search Input with glow */}
      <motion.div 
        className="relative"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="absolute inset-0 bg-gradient-to-r from-primary/20 via-accent/10 to-primary/20 rounded-2xl blur-xl -z-10" />
        <div className="relative">
          <Search className="absolute left-5 top-1/2 -translate-y-1/2 h-5 w-5 text-primary" />
          {isSearching && (
            <Loader2 className="absolute right-16 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground animate-spin" />
          )}
          <Input
            type="text"
            placeholder="Search compounds by name or category..."
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            className="pl-14 h-16 text-lg bg-card/80 backdrop-blur-sm border-border/50 rounded-2xl focus-visible:ring-primary/50 input-glow shadow-lg"
          />
          <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
            <kbd className="hidden sm:inline-flex h-7 items-center gap-1 rounded-lg border border-border/50 bg-muted/50 px-2 text-[10px] font-mono text-muted-foreground">
              <span className="text-xs">⌘</span>K
            </kbd>
          </div>
        </div>
        
        {/* Search Results Dropdown */}
        <AnimatePresence>
          {results.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -10, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.98 }}
              className="absolute top-full left-0 right-0 mt-3 z-50 glass-card rounded-2xl overflow-hidden"
            >
              {results.map((drug, index) => (
                <motion.button
                  key={drug.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  onClick={() => handleSelectDrug(drug.name)}
                  className="w-full flex items-center gap-4 px-5 py-4 hover:bg-primary/5 transition-all duration-300 text-left border-b border-border/30 last:border-0 group"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary/20 to-accent/20 text-primary group-hover:from-primary group-hover:to-accent group-hover:text-white transition-all duration-300">
                    <Pill className="h-5 w-5" />
                  </div>
                  <div className="flex-1">
                    <p className="font-semibold group-hover:text-primary transition-colors">{drug.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {drug.categories.slice(0, 2).join(" • ")}
                    </p>
                  </div>
                  <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all" />
                </motion.button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Loading State */}
      {isLoadingDrug && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center justify-center py-20"
        >
          <div className="text-center">
            <Loader2 className="h-12 w-12 text-primary mx-auto animate-spin mb-4" />
            <p className="text-muted-foreground">Loading drug information...</p>
          </div>
        </motion.div>
      )}

      {/* Selected Drug Details */}
      <AnimatePresence mode="wait">
        {selectedDrug && !isLoadingDrug && (
          <motion.div
            key={selectedDrug.name}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }}
            transition={{ duration: 0.4 }}
            className="space-y-6"
          >
            {/* Header Card */}
            <Card className="glass-card overflow-hidden">
              {/* Top gradient bar */}
              <div className="h-1 w-full bg-gradient-to-r from-primary via-accent to-info" />
              
              <div className="p-8">
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-4">
                    <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg neon-glow">
                      <Pill className="h-8 w-8 text-white" />
                    </div>
                    <div>
                      <h2 className="text-3xl font-bold gradient-text">{selectedDrug.name}</h2>
                      <p className="text-sm text-muted-foreground font-mono">{selectedDrug.id}</p>
                    </div>
                  </div>
                  <Badge 
                    variant={selectedDrug.type === 'biotech' ? 'destructive' : 'secondary'}
                    className="px-3 py-1 text-xs font-semibold"
                  >
                    {(selectedDrug.type || 'unknown').toUpperCase()}
                  </Badge>
                </div>
                <p className="text-muted-foreground text-lg leading-relaxed mb-6">{selectedDrug.description}</p>
                
                {/* Categories - Collapsible */}
                {selectedDrug.categories.length > 0 && (
                  <div className="mt-2">
                    <button
                      onClick={() => setShowCategories(!showCategories)}
                      className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <Tags className="h-4 w-4" />
                      <span>{selectedDrug.categories.length} categories</span>
                      {showCategories ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </button>
                    <AnimatePresence>
                      {showCategories && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="flex flex-wrap gap-2 mt-3 overflow-hidden"
                        >
                          {selectedDrug.categories.map((category, i) => (
                            <motion.div
                              key={category}
                              initial={{ opacity: 0, scale: 0.8 }}
                              animate={{ opacity: 1, scale: 1 }}
                              transition={{ delay: i * 0.02 }}
                            >
                              <Badge variant="outline" className="bg-primary/5 border-primary/20 hover:bg-primary/10 transition-colors text-xs">
                                {category}
                              </Badge>
                            </motion.div>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}
              </div>

              {/* Stats Row with gradient backgrounds */}
              <div className="grid grid-cols-3 border-t border-border/30">
                {[
                  { label: "Interactions", value: selectedDrug.interactionCount, color: "from-primary/10 to-transparent" },
                  { label: "Daily Doses", value: selectedDrug.dosing.timesPerDay || '-', color: "from-accent/10 to-transparent" },
                  { label: "Routes", value: selectedDrug.dosing.routes.length, color: "from-info/10 to-transparent" },
                ].map((stat, i) => (
                  <div key={stat.label} className={`p-6 text-center ${i < 2 ? 'border-r border-border/30' : ''} bg-gradient-to-b ${stat.color}`}>
                    <div className="stat-value mb-1">{stat.value}</div>
                    <div className="sci-label">{stat.label}</div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Detail Cards Grid */}
            <div className="grid md:grid-cols-2 gap-6">
              {/* Dosing Info */}
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 }}
              >
                <Card className="glass-card h-full">
                  <CardHeader className="pb-4">
                    <CardTitle className="flex items-center gap-3 text-lg">
                      <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center">
                        <Clock className="h-5 w-5 text-primary" />
                      </div>
                      Dosing Information
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {[
                      { label: "Frequency", value: selectedDrug.dosing.frequency || 'N/A' },
                      { label: "Routes", value: selectedDrug.dosing.routes.length > 0 ? selectedDrug.dosing.routes.join(', ') : 'N/A' },
                      { label: "Forms", value: selectedDrug.dosing.forms?.length > 0 ? selectedDrug.dosing.forms.join(', ') : 'N/A' },
                    ].filter(item => item.value !== 'N/A').map((item) => (
                      <div key={item.label} className="flex justify-between items-center p-3 rounded-lg bg-muted/30 border border-border/30">
                        <span className="text-sm text-muted-foreground">{item.label}</span>
                        <span className="font-semibold font-mono text-sm text-right max-w-[60%]">{item.value}</span>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </motion.div>

              {/* Physical Properties */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 }}
              >
                <Card className="glass-card h-full">
                  <CardHeader className="pb-4">
                    <CardTitle className="flex items-center gap-3 text-lg">
                      <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-accent/20 to-info/20 flex items-center justify-center">
                        <Beaker className="h-5 w-5 text-accent" />
                      </div>
                      Physical Properties
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {Object.entries(selectedDrug.properties).filter(([, value]) => value).length > 0 ? (
                      Object.entries(selectedDrug.properties).filter(([, value]) => value).map(([key, value]) => (
                        <div key={key} className="flex justify-between items-center p-3 rounded-lg bg-muted/30 border border-border/30">
                          <span className="text-sm text-muted-foreground">
                            {key.replace(/([A-Z])/g, ' $1').trim()}
                          </span>
                          <span className="font-semibold font-mono text-sm">{value || 'N/A'}</span>
                        </div>
                      ))
                    ) : (
                      <div className="p-4 rounded-lg bg-muted/30 border border-border/30 text-center text-muted-foreground text-sm">
                        No physical properties available
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>

              {/* Pharmacokinetics - Collapsible items */}
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 }}
              >
                <Card className="glass-card h-full">
                  <CardHeader className="pb-4">
                    <CardTitle className="flex items-center gap-3 text-lg">
                      <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-info/20 to-success/20 flex items-center justify-center">
                        <Activity className="h-5 w-5 text-info" />
                      </div>
                      Pharmacokinetics
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {Object.entries(selectedDrug.pharmacokinetics).filter(([, value]) => value).length > 0 ? (
                      Object.entries(selectedDrug.pharmacokinetics).filter(([, value]) => value).map(([key, value]) => (
                        <div key={key} className="rounded-lg bg-muted/30 border border-border/30 overflow-hidden">
                          <button
                            onClick={() => togglePharmacokinetics(key)}
                            className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors text-left"
                          >
                            <span className="text-sm font-medium">
                              {key.replace(/([A-Z])/g, ' $1').trim()}
                            </span>
                            {expandedPharmacokinetics.has(key) ? (
                              <ChevronDown className="h-4 w-4 text-muted-foreground" />
                            ) : (
                              <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            )}
                          </button>
                          <AnimatePresence>
                            {expandedPharmacokinetics.has(key) && (
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="overflow-hidden"
                              >
                                <div className="px-3 pb-3 text-sm text-muted-foreground border-t border-border/30 pt-2">
                                  {value || 'N/A'}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      ))
                    ) : (
                      <div className="p-4 rounded-lg bg-muted/30 border border-border/30 text-center text-muted-foreground text-sm">
                        No pharmacokinetics data available
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>

              {/* Interactions Warning - Expandable */}
              {selectedDrug.interactionCount > 0 && (
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 }}
                >
                  <Card className="glass-card h-full border-warning/30 overflow-hidden">
                    <div className="h-1 w-full bg-gradient-to-r from-warning to-destructive" />
                    <CardHeader className="pb-2">
                      <button 
                        onClick={() => setShowInteractions(!showInteractions)}
                        className="w-full flex items-center justify-between text-left"
                      >
                        <CardTitle className="flex items-center gap-3 text-lg text-warning">
                          <div className="h-10 w-10 rounded-xl bg-warning/20 flex items-center justify-center">
                            <AlertCircle className="h-5 w-5 text-warning" />
                          </div>
                          Interaction Alert
                          <Badge variant="outline" className="ml-2 bg-warning/10 text-warning border-warning/30">
                            {selectedDrug.interactionCount}
                          </Badge>
                        </CardTitle>
                        <div className="flex items-center gap-2 text-muted-foreground text-sm">
                          <span>{showInteractions ? 'Hide' : 'Show'}</span>
                          {showInteractions ? (
                            <ChevronDown className="h-5 w-5 text-warning" />
                          ) : (
                            <ChevronRight className="h-5 w-5 text-warning" />
                          )}
                        </div>
                      </button>
                    </CardHeader>
                    <CardContent>
                      {/* Food Tips - Always visible, clickable separately */}
                      {selectedDrug.foodInteractions && selectedDrug.foodInteractions.length > 0 && (
                        <div className="mb-4">
                          <button
                            onClick={(e) => { e.stopPropagation(); setShowFoodInteractions(!showFoodInteractions); }}
                            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 transition-colors"
                          >
                            <span className="text-sm">🍽️</span>
                            <span className="text-xs font-medium text-amber-600">
                              {selectedDrug.foodInteractions.length} Food Tips
                            </span>
                            {showFoodInteractions ? (
                              <ChevronDown className="h-3 w-3 text-amber-600" />
                            ) : (
                              <ChevronRight className="h-3 w-3 text-amber-600" />
                            )}
                          </button>
                          <AnimatePresence>
                            {showFoodInteractions && (
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="mt-2 space-y-2"
                              >
                                {selectedDrug.foodInteractions.map((tip, idx) => (
                                  <div key={idx} className="p-3 rounded-lg bg-muted/30 border border-border/30">
                                    <p className="text-xs text-muted-foreground leading-relaxed">{tip}</p>
                                  </div>
                                ))}
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      )}

                      {/* Drug Interactions - expandable */}
                      <AnimatePresence>
                        {showInteractions && selectedDrug.interactions && selectedDrug.interactions.length > 0 && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="mb-4"
                          >
                            <ScrollArea className="h-[250px] pr-4">
                              <div className="space-y-2">
                                {selectedDrug.interactions.slice(0, interactionsLimit).map((interaction, idx) => (
                                  <div 
                                    key={idx} 
                                    className="p-3 rounded-lg bg-muted/30 border border-border/30"
                                  >
                                    <span className="font-semibold text-sm text-primary">{interaction.drugName}</span>
                                    <p className="text-xs text-muted-foreground mt-1">
                                      {interaction.description}
                                    </p>
                                  </div>
                                ))}
                                {selectedDrug.interactions.length > interactionsLimit && (
                                  <div className="flex flex-col items-center gap-2 py-3">
                                    <p className="text-xs text-muted-foreground">
                                      Showing {interactionsLimit} of {selectedDrug.interactions.length}
                                    </p>
                                    <button
                                      onClick={() => setInteractionsLimit(prev => Math.min(prev + 100, selectedDrug.interactions.length))}
                                      className="px-4 py-2 text-xs font-medium bg-primary/10 hover:bg-primary/20 text-primary rounded-lg transition-colors"
                                    >
                                      Load {Math.min(100, selectedDrug.interactions.length - interactionsLimit)} More
                                    </button>
                                    {interactionsLimit < selectedDrug.interactions.length && (
                                      <button
                                        onClick={() => setInteractionsLimit(selectedDrug.interactions.length)}
                                        className="text-xs text-muted-foreground hover:text-primary underline"
                                      >
                                        Show All ({selectedDrug.interactions.length})
                                      </button>
                                    )}
                                  </div>
                                )}
                              </div>
                            </ScrollArea>
                          </motion.div>
                        )}
                      </AnimatePresence>
                      {!showInteractions && (
                        <p className="text-muted-foreground text-sm leading-relaxed">
                          Click to view {selectedDrug.interactionCount} drug interactions.
                        </p>
                      )}
                      <div className="mt-4 p-3 rounded-lg bg-warning/5 border border-warning/20">
                        <div className="flex items-center gap-2 text-sm text-warning">
                          <Sparkles className="h-4 w-4" />
                          <span className="font-medium">Use Compatibility Analysis for detailed checks</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty State */}
      {!selectedDrug && !isLoadingDrug && (
        <motion.div 
          className="text-center py-20"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <div className="relative inline-block mb-6">
            <div className="h-24 w-24 rounded-3xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center">
              <Pill className="h-12 w-12 text-primary" />
            </div>
            <div className="absolute inset-0 rounded-3xl bg-primary/10 blur-2xl -z-10" />
          </div>
          <h3 className="text-2xl font-bold mb-3 gradient-text">Search Compounds</h3>
          <p className="text-muted-foreground max-w-md mx-auto leading-relaxed">
            Enter a compound name or category to access detailed information including 
            dosing parameters, physicochemical properties, and interaction data.
          </p>
        </motion.div>
      )}
    </div>
  );
}
