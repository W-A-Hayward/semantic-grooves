"use client"

import { useState } from "react"
import type { AlbumResult } from "@/lib/mock-data"
import { ScoreRing } from "./score-ring"
import { EqualizerBars } from "./equalizer-bars"
import { Award, Tag, Calendar, Disc, User } from "lucide-react"

interface ResultCardProps {
  result: AlbumResult
  index: number
}

export function ResultCard({ result, index }: ResultCardProps) {
  const [isHovered, setIsHovered] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)

  const matchPercentage = Math.round(result.matchScore * 100)

  const matchTypeLabel = {
    semantic: "SEM",
    lexical: "LEX",
    hybrid: "HYB",
  }

  const matchTypeColor = {
    semantic: "var(--burnt-peach)",
    lexical: "var(--rosy-taupe)",
    hybrid: "var(--powder-petal)",
  }

  return (
    <div
      className="relative group cursor-pointer"
      style={{
        animationDelay: `${index * 100}ms`,
        animationFillMode: "forwards",
        opacity: 0,
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => setIsExpanded(!isExpanded)}
    >
      {/* Card */}
      <div
        className="animate-fade-in-up relative rounded-lg border overflow-hidden transition-all duration-300"
        style={{
          animationDelay: `${index * 100}ms`,
          backgroundColor: isHovered ? "hsl(12 8% 14%)" : "hsl(12 8% 12%)",
          borderColor: isHovered ? "var(--terracotta-clay)" : "hsl(12 8% 20%)",
        }}
      >
        {/* Match score bar at top */}
        <div className="h-[2px] w-full" style={{ backgroundColor: "hsl(12 8% 18%)" }}>
          <div
            className="h-full transition-all duration-1000 ease-out"
            style={{
              width: `${matchPercentage}%`,
              backgroundColor: matchTypeColor[result.matchType],
              transitionDelay: `${index * 100 + 300}ms`,
            }}
          />
        </div>

        <div className="p-5">
          {/* Top row: rank + match info */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span
                className="font-mono text-[10px] uppercase tracking-widest"
                style={{ color: "var(--rosy-taupe)" }}
              >
                #{String(index + 1).padStart(2, "0")}
              </span>
              <span
                className="px-2 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider font-bold"
                style={{
                  backgroundColor: `${matchTypeColor[result.matchType]}15`,
                  color: matchTypeColor[result.matchType],
                  border: `1px solid ${matchTypeColor[result.matchType]}30`,
                }}
              >
                {matchTypeLabel[result.matchType]} {matchPercentage}%
              </span>
              {result.bestNewMusic && (
                <span
                  className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider"
                  style={{
                    backgroundColor: "var(--burnt-peach)",
                    color: "hsl(12 8% 10%)",
                  }}
                >
                  <Award size={10} />
                  BNM
                </span>
              )}
            </div>
            <EqualizerBars active={isHovered} barCount={4} className="h-4" />
          </div>

          {/* Main content */}
          <div className="flex gap-5">
            {/* Album art placeholder - vinyl aesthetic */}
            <div
              className="relative flex-shrink-0 w-20 h-20 rounded overflow-hidden flex items-center justify-center"
              style={{ backgroundColor: "hsl(12 8% 8%)" }}
            >
              <div
                className={`transition-transform duration-700 ${isHovered ? "rotate-[30deg]" : ""}`}
              >
                <Disc size={40} style={{ color: "var(--terracotta-clay)" }} strokeWidth={1} />
              </div>
              {/* Genre badge on art */}
              <span
                className="absolute bottom-1 left-1 right-1 text-center text-[7px] font-mono uppercase tracking-wider py-0.5 rounded"
                style={{
                  backgroundColor: "hsl(12 8% 8% / 0.9)",
                  color: "var(--rosy-taupe)",
                }}
              >
                {result.genre.split(" / ")[0]}
              </span>
            </div>

            {/* Text content */}
            <div className="flex-1 min-w-0">
              <h3
                className="font-mono text-base font-bold leading-tight truncate"
                style={{ color: "var(--seashell)" }}
              >
                {result.album}
              </h3>
              <p
                className="font-mono text-sm mt-0.5 truncate"
                style={{ color: "var(--burnt-peach)" }}
              >
                {result.artist}
              </p>
              <div className="flex items-center gap-3 mt-2">
                <span
                  className="flex items-center gap-1 text-[10px] font-mono"
                  style={{ color: "var(--rosy-taupe)" }}
                >
                  <Calendar size={10} />
                  {result.year}
                </span>
                <span
                  className="flex items-center gap-1 text-[10px] font-mono"
                  style={{ color: "var(--rosy-taupe)" }}
                >
                  <Tag size={10} />
                  {result.label}
                </span>
                <span
                  className="flex items-center gap-1 text-[10px] font-mono"
                  style={{ color: "var(--rosy-taupe)" }}
                >
                  <User size={10} />
                  {result.reviewer}
                </span>
              </div>
            </div>

            {/* Score */}
            <div className="flex-shrink-0">
              <ScoreRing score={result.score} size={56} />
            </div>
          </div>

          {/* Review excerpt - expandable */}
          <div
            className="overflow-hidden transition-all duration-500 ease-out"
            style={{
              maxHeight: isExpanded ? "200px" : "0px",
              opacity: isExpanded ? 1 : 0,
            }}
          >
            <div className="mt-4 pt-4" style={{ borderTop: "1px solid hsl(12 8% 20%)" }}>
              <p
                className="font-mono text-xs leading-relaxed"
                style={{ color: "var(--powder-petal)" }}
              >
                {'"'}
                {result.reviewExcerpt}
                {'"'}
              </p>
              <p
                className="mt-2 text-[10px] font-mono uppercase tracking-wider"
                style={{ color: "var(--rosy-taupe)" }}
              >
                {'-- '}{result.reviewer}, Pitchfork
              </p>
            </div>
          </div>

          {/* Expand hint */}
          <div className="mt-3 text-center">
            <span
              className="text-[9px] font-mono uppercase tracking-widest transition-colors duration-200"
              style={{ color: isHovered ? "var(--burnt-peach)" : "hsl(12 8% 25%)" }}
            >
              {isExpanded ? "[ collapse ]" : "[ read review ]"}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
