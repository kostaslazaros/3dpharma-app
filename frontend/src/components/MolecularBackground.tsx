import { useEffect, useRef } from "react";
import { motion } from "framer-motion";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  connections: number[];
}

export function MolecularBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationId: number;
    let particles: Particle[] = [];

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    const createParticles = () => {
      const count = Math.floor((canvas.width * canvas.height) / 25000);
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        radius: Math.random() * 2 + 1,
        connections: [],
      }));
    };

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Update and draw particles
      particles.forEach((p, i) => {
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

        // Draw particle with soft glow
        const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.radius * 3);
        gradient.addColorStop(0, "rgba(59, 130, 246, 0.6)");
        gradient.addColorStop(0.5, "rgba(59, 130, 246, 0.2)");
        gradient.addColorStop(1, "rgba(59, 130, 246, 0)");
        
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * 3, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(59, 130, 246, 0.7)";
        ctx.fill();

        // Draw connections
        particles.forEach((p2, j) => {
          if (i >= j) return;
          const dx = p.x - p2.x;
          const dy = p.y - p2.y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < 120) {
            const opacity = (1 - distance / 120) * 0.25;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = `rgba(59, 130, 246, ${opacity})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        });
      });

      animationId = requestAnimationFrame(animate);
    };

    resize();
    createParticles();
    animate();

    window.addEventListener("resize", () => {
      resize();
      createParticles();
    });

    return () => {
      cancelAnimationFrame(animationId);
    };
  }, []);

  return (
    <>
      <canvas
        ref={canvasRef}
        className="fixed inset-0 pointer-events-none z-0"
        style={{ opacity: 0.4 }}
      />
      {/* Gradient overlays for clean fade */}
      <div className="fixed inset-0 pointer-events-none z-0 bg-gradient-to-b from-background via-transparent to-background opacity-80" />
      <div className="fixed inset-0 pointer-events-none z-0 bg-gradient-to-r from-background via-transparent to-background opacity-40" />
    </>
  );
}

export function FloatingMolecule({ className = "", delay = 0 }: { className?: string; delay?: number }) {
  return (
    <motion.div
      className={`absolute pointer-events-none ${className}`}
      initial={{ opacity: 0, scale: 0.5 }}
      animate={{ 
        opacity: [0.3, 0.6, 0.3],
        scale: [1, 1.1, 1],
        rotate: [0, 180, 360],
      }}
      transition={{
        duration: 20,
        delay,
        repeat: Infinity,
        ease: "linear",
      }}
    >
      <svg viewBox="0 0 100 100" className="w-full h-full">
        <defs>
          <radialGradient id={`glow-${delay}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="hsl(221 83% 53%)" stopOpacity="0.4" />
            <stop offset="100%" stopColor="hsl(221 83% 53%)" stopOpacity="0" />
          </radialGradient>
        </defs>
        {/* Central atom */}
        <circle cx="50" cy="50" r="8" fill="hsl(221 83% 53%)" />
        <circle cx="50" cy="50" r="12" fill={`url(#glow-${delay})`} />
        {/* Orbital electrons */}
        <circle cx="50" cy="20" r="4" fill="hsl(173 80% 40%)" />
        <circle cx="76" cy="65" r="4" fill="hsl(173 80% 40%)" />
        <circle cx="24" cy="65" r="4" fill="hsl(173 80% 40%)" />
        {/* Bonds */}
        <line x1="50" y1="42" x2="50" y2="24" stroke="hsl(221 60% 70%)" strokeWidth="2" />
        <line x1="56" y1="54" x2="72" y2="63" stroke="hsl(221 60% 70%)" strokeWidth="2" />
        <line x1="44" y1="54" x2="28" y2="63" stroke="hsl(221 60% 70%)" strokeWidth="2" />
      </svg>
    </motion.div>
  );
}

export function DNAHelix() {
  return (
    <motion.div
      className="absolute right-0 top-1/4 w-32 h-96 pointer-events-none opacity-20"
      animate={{ rotateY: 360 }}
      transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
    >
      {Array.from({ length: 20 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-full flex justify-between items-center"
          style={{ top: `${i * 5}%` }}
          animate={{
            x: [Math.sin(i * 0.5) * 20, Math.sin(i * 0.5 + Math.PI) * 20, Math.sin(i * 0.5) * 20],
          }}
          transition={{ duration: 4, repeat: Infinity, delay: i * 0.1 }}
        >
          <div className="w-3 h-3 rounded-full bg-primary/60" />
          <div className="flex-1 h-px bg-gradient-to-r from-primary/40 via-accent/40 to-info/40 mx-1" />
          <div className="w-3 h-3 rounded-full bg-info/60" />
        </motion.div>
      ))}
    </motion.div>
  );
}
