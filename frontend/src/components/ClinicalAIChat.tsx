import { useState, useEffect } from "react";
import { Send, Bot, User, Stethoscope, Loader2, Zap, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { sendCoAdminChat, getCoAdminStatus } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const exampleQuestions = [
  "Can I give ibuprofen to a pregnant patient also on lisinopril?",
  "Is primaquine safe for a patient with G6PD deficiency?",
  "Warfarin and aspirin together — what should I watch for?",
  "Any concern giving metronidazole to a patient who drinks alcohol?",
];

export function ClinicalAIChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isApiAvailable, setIsApiAvailable] = useState<boolean | null>(null);
  const [apiMessage, setApiMessage] = useState("");
  const [modelInfo, setModelInfo] = useState("");

  useEffect(() => {
    async function checkApi() {
      try {
        const status = await getCoAdminStatus();
        setIsApiAvailable(status.available);
        setApiMessage(status.message);
        setModelInfo(`${status.provider} · ${status.model}`);
      } catch {
        setIsApiAvailable(false);
        setApiMessage("Backend API not available. Please ensure the FastAPI server is running.");
      }
    }
    checkApi();
  }, []);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    const currentInput = input;
    setInput("");
    setIsLoading(true);

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const response = await sendCoAdminChat(currentInput, history);
      setMessages((prev) => [...prev, { role: "assistant", content: response.response }]);
    } catch (error) {
      console.error("Clinical chat error:", error);
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: `Error: ${error instanceof Error ? error.message : "Failed to get response from the server. Please make sure the backend is running."}`,
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const formatMessageContent = (content: string) => {
    return content
      .replace(/^## /gm, '<h3 class="text-base font-semibold gradient-text mt-0 mb-2">')
      .replace(/^### /gm, '<h4 class="text-sm font-semibold mt-2 mb-1">')
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/_([^_]+)_/g, '<em class="text-muted-foreground">$1</em>')
      .replace(/\n/g, "<br/>")
      .replace(/<h3[^>]*>([^<]*)/g, '<h3 class="text-base font-semibold gradient-text mt-4 mb-2">$1</h3>')
      .replace(/<h4[^>]*>([^<]*)/g, '<h4 class="text-sm font-semibold mt-3 mb-1">$1</h4>');
  };

  return (
    <div className="flex flex-col h-[calc(100vh-12rem)] max-h-[700px]">
      {isApiAvailable === false && (
        <motion.div
          initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
          className="mb-4 p-4 rounded-xl bg-warning/10 border border-warning/30 flex items-center gap-3"
        >
          <AlertCircle className="h-5 w-5 text-warning shrink-0" />
          <div className="text-sm">
            <p className="font-medium text-warning">Clinical AI Unavailable</p>
            <p className="text-muted-foreground">{apiMessage}</p>
          </div>
        </motion.div>
      )}

      <ScrollArea className="flex-1 pr-4">
        <div className="space-y-4 pb-4">
          {messages.length === 0 && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center py-12">
              <div className="relative inline-block mb-6">
                <div className="h-20 w-20 rounded-3xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg">
                  <Stethoscope className="h-10 w-10 text-white" />
                </div>
                <div className="absolute inset-0 rounded-3xl bg-primary/20 blur-2xl -z-10" />
              </div>
              <h3 className="text-2xl font-bold mb-3 gradient-text">Clinical AI Assistant</h3>
              <p className="text-muted-foreground max-w-md mx-auto mb-2">
                Ask about co-administration, contraindications by patient condition, and safer
                alternatives. Answers are grounded in openFDA labels and DrugBank data.
              </p>
              {modelInfo && <p className="text-xs text-muted-foreground/70 mb-8">Model: {modelInfo}</p>}
              <div className="flex flex-wrap justify-center gap-3">
                {exampleQuestions.map((q) => (
                  <button
                    key={q}
                    onClick={() => setInput(q)}
                    disabled={isApiAvailable === false}
                    className="px-4 py-3 text-sm rounded-xl glass-card hover:border-primary/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed max-w-xs text-left"
                  >
                    <Zap className="h-3 w-3 inline mr-2 text-primary" />{q}
                  </button>
                ))}
              </div>
            </motion.div>
          )}

          <AnimatePresence>
            {messages.map((message, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                className={cn("flex gap-3", message.role === "user" && "flex-row-reverse")}
              >
                <div className={cn(
                  "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                  message.role === "user" ? "bg-gradient-to-br from-primary to-accent" : "bg-muted"
                )}>
                  {message.role === "user" ? <User className="h-5 w-5 text-white" /> : <Bot className="h-5 w-5" />}
                </div>
                <Card className={cn(
                  "max-w-[80%] p-5 rounded-2xl",
                  message.role === "user" ? "bg-gradient-to-br from-primary to-accent text-white" : "glass-card"
                )}>
                  {message.role === "assistant" ? (
                    <div className="prose prose-sm dark:prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: formatMessageContent(message.content) }} />
                  ) : (
                    <p className="text-sm">{message.content}</p>
                  )}
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>

          {isLoading && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-muted">
                <Bot className="h-5 w-5" />
              </div>
              <Card className="p-5 glass-card rounded-2xl">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Checking labels &amp; interactions…
                </div>
              </Card>
            </motion.div>
          )}
        </div>
      </ScrollArea>

      <div className="pt-4 border-t border-border/30">
        <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="flex gap-3">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={isApiAvailable === false ? "Clinical AI unavailable…" : "Ask about co-administration, contraindications, alternatives…"}
            className="flex-1 h-14 bg-card/80 backdrop-blur-sm border-border/50 rounded-xl"
            disabled={isLoading || isApiAvailable === false}
          />
          <Button
            type="submit" size="lg"
            disabled={!input.trim() || isLoading || isApiAvailable === false}
            className="h-14 px-6 rounded-xl bg-gradient-to-r from-primary to-accent hover:opacity-90"
          >
            <Send className="h-5 w-5" />
          </Button>
        </form>
      </div>
    </div>
  );
}
