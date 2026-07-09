import { Menu, X, Zap, Pill } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface HeaderProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const tabs = [
  { id: "search", label: "Compound Search", code: "01", icon: "🔬" },
  { id: "compatibility", label: "Compatibility", code: "02", icon: "⚗️" },
  { id: "coadmin", label: "Co-administration", code: "03", icon: "🩺" },
  { id: "clinical-ai", label: "Clinical AI", code: "04", icon: "🧠" },
  { id: "chat", label: "Printability AI", code: "05", icon: "🖨️" },
  { id: "categories", label: "Classification", code: "06", icon: "📊" },
];

export function Header({ activeTab, onTabChange }: HeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/50 bg-background/80 backdrop-blur-xl">
      {/* Top accent line */}
      <div className="h-px w-full bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
      
      <div className="container flex h-16 items-center justify-between px-4">
        {/* Logo */}
        <motion.div 
          className="flex items-center gap-3"
          whileHover={{ scale: 1.02 }}
          transition={{ type: "spring", stiffness: 400 }}
        >
          <div className="relative">
            {/* Pill in dark purple (same as footer) */}
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-800 shadow-lg">
              <Pill className="h-5 w-5 text-white" />
            </div>
          </div>
          <div className="hidden sm:block">
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight gradient-text">
                DCAS
              </h1>
              <div className="hidden md:flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground bg-muted/50 px-2 py-1 rounded-full border border-border/50">
                <Zap className="h-3 w-3 text-primary" />
                <span>Drug Compatibility Analysis</span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-1 p-1 bg-muted/30 rounded-full border border-border/50">
          {tabs.map((tab) => (
            <motion.button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={cn(
                "relative px-4 py-2 text-sm font-medium transition-all duration-300 rounded-full",
                activeTab === tab.id
                  ? "text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {activeTab === tab.id && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute inset-0 rounded-full bg-gradient-to-r from-primary to-accent shadow-lg"
                  transition={{ type: "spring", bounce: 0.15, duration: 0.5 }}
                />
              )}
              <span className="relative z-10 flex items-center gap-2">
                <span className="text-xs">{tab.icon}</span>
                <span className="hidden lg:inline">{tab.label}</span>
                <span className="lg:hidden font-mono text-[10px] opacity-70">{tab.code}</span>
              </span>
            </motion.button>
          ))}
        </nav>

        {/* Atherosclerosis Button - commented out (athero app not in repo)
        <motion.button
          onClick={() => onTabChange("athero")}
          className={cn(
            "hidden md:flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg border transition-all duration-300",
            activeTab === "athero"
              ? "bg-red-500/10 border-red-500/30 text-red-600"
              : "bg-muted/30 border-border/50 text-muted-foreground hover:text-foreground hover:border-red-500/30"
          )}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <span>❤️</span>
          <span className="hidden lg:inline">Athero</span>
        </motion.button>
        */}

        {/* Mobile Menu Button */}
        <motion.button
          className="md:hidden flex h-10 w-10 items-center justify-center rounded-xl bg-muted/50 border border-border/50"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          whileTap={{ scale: 0.95 }}
        >
          {mobileMenuOpen ? (
            <X className="h-5 w-5" />
          ) : (
            <Menu className="h-5 w-5" />
          )}
        </motion.button>
      </div>

      {/* Mobile Navigation */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.nav
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden border-t border-border/50 bg-card/95 backdrop-blur-xl"
          >
            <div className="container px-4 py-3 space-y-1">
              {tabs.map((tab, index) => (
                <motion.button
                  key={tab.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  onClick={() => {
                    onTabChange(tab.id);
                    setMobileMenuOpen(false);
                  }}
                  className={cn(
                    "w-full text-left px-4 py-3 text-sm font-medium transition-all duration-300 rounded-xl flex items-center gap-3",
                    activeTab === tab.id
                      ? "text-primary-foreground bg-gradient-to-r from-primary to-accent shadow-lg"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                  )}
                >
                  <span className="text-base">{tab.icon}</span>
                  <span className="font-mono text-[10px] opacity-60 w-6">{tab.code}</span>
                  <span>{tab.label}</span>
                </motion.button>
              ))}
              {/* Atherosclerosis - commented out (athero app not in repo)
              <div className="border-t border-border/50 pt-2 mt-2">
                <motion.button
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: tabs.length * 0.05 }}
                  onClick={() => {
                    onTabChange("athero");
                    setMobileMenuOpen(false);
                  }}
                  className={cn(
                    "w-full text-left px-4 py-3 text-sm font-medium transition-all duration-300 rounded-xl flex items-center gap-3",
                    activeTab === "athero"
                      ? "bg-red-500/10 text-red-600 border border-red-500/30"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                  )}
                >
                  <span className="text-base">❤️</span>
                  <span>Atherosclerosis Research</span>
                </motion.button>
              </div>
              */}
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}
