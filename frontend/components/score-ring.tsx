"use client"

import { useEffect, useState } from "react"

interface ScoreRingProps {
  score: number
  size?: number
  className?: string
}

export function ScoreRing({ score, size = 64, className = "" }: ScoreRingProps) {
  const [mounted, setMounted] = useState(false)
  const radius = 28
  const circumference = 2 * Math.PI * radius
  const progress = (score / 10) * circumference
  const offset = circumference - progress

  useEffect(() => {
    setMounted(true)
  }, [])

  const getScoreColor = (s: number) => {
    if (s >= 9.0) return "var(--burnt-peach)"
    if (s >= 8.0) return "var(--rosy-taupe)"
    if (s >= 7.0) return "var(--powder-petal)"
    return "var(--seashell)"
  }

  return (
    <div className={`relative inline-flex items-center justify-center ${className}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 64 64" style={{ width: size, height: size }}>
        {/* Background ring */}
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          stroke="hsl(12 8% 18%)"
          strokeWidth="3"
        />
        {/* Progress ring */}
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          stroke={getScoreColor(score)}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={mounted ? offset : circumference}
          transform="rotate(-90 32 32)"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <span
        className="absolute font-mono font-bold"
        style={{
          color: getScoreColor(score),
          fontSize: size * 0.25,
        }}
      >
        {score.toFixed(1)}
      </span>
    </div>
  )
}
