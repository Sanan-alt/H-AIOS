import { cn } from "@/lib/utils";
import type { HaroidState } from "@/hooks/use-haroid-socket";

export function Reactor({ state }: { state: HaroidState }) {
  return (
    <div className={cn("reactor", `reactor-${state.toLowerCase()}`)} aria-label={`HAROID state: ${state}`} role="img">
      <div className="reactor-orbit orbit-a" />
      <div className="reactor-orbit orbit-b" />
      <div className="reactor-spokes" />
      <div className="reactor-core"><span>J</span></div>
    </div>
  );
}
