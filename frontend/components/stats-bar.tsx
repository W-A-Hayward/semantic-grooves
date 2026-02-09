"use client"

import { Database, Zap, Layers } from "lucide-react"

interface StatsBarProps {
  resultCount: number
  queryTime?: number
  visible: boolean
}

export function StatsBar({ resultCount, queryTime = 0.42, visible }: StatsBarProps) {
  if (!visible) return null

  return (
    <div
      className="flex items-center justify-center gap-6 py-3 animate-fade-in-up"
      style={{ animationDelay: "0ms" }}
    >
      <div className="flex items-center gap-2">
        <Database size={12} style={{ color: "var(--rosy-taupe)" }} />
        <span
          className="font-mono text-[10px] uppercase tracking-wider"
          style={{ color: "var(--rosy-taupe)" }}
        >
          {resultCount} matches
        </span>
      </div>
      <span style={{ color: "hsl(12 8% 25%)" }}>|</span>
      <div className="flex items-center gap-2">
        <Zap size={12} style={{ color: "var(--burnt-peach)" }} />
        <span
          className="font-mono text-[10px] uppercase tracking-wider"
          style={{ color: "var(--rosy-taupe)" }}
        >
          {queryTime.toFixed(2)}s
        </span>
      </div>
      <span style={{ color: "hsl(12 8% 25%)" }}>|</span>
      <div className="flex items-center gap-2">
        <Layers size={12} style={{ color: "var(--rosy-taupe)" }} />
        <span
          className="font-mono text-[10px] uppercase tracking-wider"
          style={{ color: "var(--rosy-taupe)" }}
        >
          hybrid search
        </span>
      </div>
    </div>
  )
}
