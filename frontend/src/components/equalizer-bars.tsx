"use client"

import { useEffect, useRef } from "react"

interface EqualizerBarsProps {
  barCount?: number
  active?: boolean
  className?: string
  color?: string
}

export function EqualizerBars({
  barCount = 5,
  active = true,
  className = "",
  color = "var(--burnt-peach)",
}: EqualizerBarsProps) {
  const barsRef = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    if (!active) return

    const intervals: NodeJS.Timeout[] = []

    barsRef.current.forEach((bar, i) => {
      if (!bar) return
      const animate = () => {
        const height = Math.random() * 24 + 4
        bar.style.height = `${height}px`
      }
      animate()
      intervals.push(setInterval(animate, 200 + i * 50))
    })

    return () => intervals.forEach(clearInterval)
  }, [active])

  return (
    <div className={`flex items-end gap-[2px] ${className}`}>
      {Array.from({ length: barCount }).map((_, i) => (
        <div
          key={i}
          ref={(el) => {
            barsRef.current[i] = el
          }}
          className="w-[3px] rounded-full transition-all duration-200 ease-out"
          style={{
            backgroundColor: color,
            height: active ? "4px" : "4px",
            opacity: active ? 1 : 0.3,
          }}
        />
      ))}
    </div>
  )
}
