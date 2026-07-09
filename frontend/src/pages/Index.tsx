import { useState } from "react";
import { motion } from "framer-motion";
import { Atom, Database, Sparkles, Zap, FlaskConical, Pill, Stethoscope } from "lucide-react";
import { Header } from "@/components/Header";
import { DrugSearch } from "@/components/DrugSearch";
import { CompatibilityCheck } from "@/components/CompatibilityCheck";
import { CoAdministration } from "@/components/CoAdministration";
import { ClinicalAIChat } from "@/components/ClinicalAIChat";
import { AIChat } from "@/components/AIChat";
import { DrugCategories } from "@/components/DrugCategories";
import { MolecularBackground, FloatingMolecule } from "@/components/MolecularBackground";
// import { AtheroscleresisDashboard } from "@/components/AtheroscleresisDashboard"; // athero app not in repo

const Index = () => {
  const [activeTab, setActiveTab] = useState("search");

  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      {/* Animated molecular background */}
      <MolecularBackground />
      
      {/* Floating molecules decoration */}
      <FloatingMolecule className="w-24 h-24 top-20 left-10" delay={0} />
      <FloatingMolecule className="w-16 h-16 top-40 right-20" delay={2} />
      <FloatingMolecule className="w-20 h-20 bottom-40 left-1/4" delay={4} />
      
      {/* Deep purple gradient orbs */}
      <div className="fixed top-0 left-1/4 w-[600px] h-[600px] bg-primary/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="fixed bottom-0 right-1/4 w-[500px] h-[500px] bg-accent/10 rounded-full blur-[100px] pointer-events-none" />
      <div className="fixed top-1/2 right-10 w-[300px] h-[300px] bg-info/8 rounded-full blur-[80px] pointer-events-none" />

      <Header activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="container px-4 py-8 relative z-10">
        {/* Hero Section - Only on search tab */}
        {activeTab === "search" && (
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="mb-12"
          >
            <div className="text-center max-w-3xl mx-auto mb-12">
              {/* Research badge with glow */}
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.2 }}
                className="inline-flex items-center gap-2 research-badge mb-6"
              >
                <Zap className="h-3.5 w-3.5" />
                <span className="uppercase tracking-[0.2em] text-[10px] font-semibold">
                  3D Pharmaceutical Research Platform
                </span>
              </motion.div>
              
              {/* Main title with gradient */}
              <motion.h1 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="text-4xl md:text-6xl font-bold tracking-tight mb-4"
              >
                <span className="text-foreground">Drug Compatibility</span>
                <br />
                <span className="gradient-text">Analysis System</span>
              </motion.h1>
              
              {/* Subtitle */}
              <motion.p 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
                className="text-muted-foreground text-lg leading-relaxed max-w-xl mx-auto"
              >
                Advanced compound analysis for additive manufacturing. 
                Evaluate interactions, physicochemical properties, and formulation parameters.
              </motion.p>

              {/* Decorative line */}
              <motion.div
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ delay: 0.5, duration: 0.8 }}
                className="mt-8 h-px w-48 mx-auto bg-gradient-to-r from-transparent via-primary/50 to-transparent"
              />
            </div>
          </motion.div>
        )}

        {/* Tab Headers with icons */}
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mb-8"
        >
          {activeTab === "compatibility" && (
            <div className="flex items-center gap-4 mb-8">
              <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-primary to-info flex items-center justify-center shadow-lg neon-glow">
                <Atom className="h-7 w-7 text-white animate-spin-slow" />
              </div>
              <div>
                <h2 className="text-3xl font-bold gradient-text">Compatibility Analysis</h2>
                <p className="text-muted-foreground">
                  Check drug-drug interactions and 3D printing compatibility
                </p>
              </div>
            </div>
          )}
          {activeTab === "coadmin" && (
            <div className="flex items-center gap-4 mb-8">
              <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg neon-glow">
                <Stethoscope className="h-7 w-7 text-white" />
              </div>
              <div>
                <h2 className="text-3xl font-bold gradient-text">Co-administration Check</h2>
                <p className="text-muted-foreground">
                  Clinical contraindications, interactions, and adverse effects by patient condition
                </p>
              </div>
            </div>
          )}
          {activeTab === "clinical-ai" && (
            <div className="flex items-center gap-4 mb-8">
              <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg neon-glow">
                <Sparkles className="h-7 w-7 text-white" />
              </div>
              <div>
                <h2 className="text-3xl font-bold gradient-text">Clinical AI Assistant</h2>
                <p className="text-muted-foreground">
                  Grounded co-administration Q&amp;A — contraindications, interactions, alternatives
                </p>
              </div>
            </div>
          )}
          {activeTab === "chat" && (
            <div className="flex items-center gap-4 mb-8">
              <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-accent to-info flex items-center justify-center shadow-lg neon-glow">
                <Sparkles className="h-7 w-7 text-white" />
              </div>
              <div>
                <h2 className="text-3xl font-bold gradient-text">Printability AI</h2>
                <p className="text-muted-foreground">
                  3D-printing compatibility, physical properties, and formulation guidance
                </p>
              </div>
            </div>
          )}
          {activeTab === "categories" && (
            <div className="flex items-center gap-4 mb-8">
              <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-warning to-destructive flex items-center justify-center shadow-lg neon-glow">
                <Database className="h-7 w-7 text-white" />
              </div>
              <div>
                <h2 className="text-3xl font-bold gradient-text">Drug Classification</h2>
                <p className="text-muted-foreground">
                  Browse compounds by therapeutic category
                </p>
              </div>
            </div>
          )}
        </motion.div>

        {/* Atherosclerosis Dashboard - commented out (athero app not in repo)
        {activeTab === "athero" && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="-mx-4 -mt-8"
          >
            <AtheroscleresisDashboard />
          </motion.div>
        )}
        */}

        {/* Content with animation */}
        <motion.div
            key={`content-${activeTab}`}
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
          >
            {activeTab === "search" && <DrugSearch />}
            {activeTab === "compatibility" && <CompatibilityCheck />}
            {activeTab === "coadmin" && <CoAdministration />}
            {activeTab === "clinical-ai" && <ClinicalAIChat />}
            {activeTab === "chat" && <AIChat />}
            {activeTab === "categories" && <DrugCategories />}
          </motion.div>
        {/* Footer spacer */}
        <div className="h-20" />
      </main>

      {/* Fixed Footer */}
      <footer className="fixed bottom-0 left-0 right-0 z-50 border-t border-primary/20 py-3 bg-card/98 backdrop-blur-xl shadow-lg">
        <div className="container px-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Pill icon in dark purple */}
              <div className="h-8 w-8 rounded-lg bg-purple-800 flex items-center justify-center shadow-lg">
                <Pill className="h-4 w-4 text-white" />
              </div>
              <span className="text-sm font-medium text-foreground">DCAS</span>
            </div>
            
            <p className="text-xs text-muted-foreground font-mono tracking-wide">
              FOR RESEARCH USE ONLY
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Index;
