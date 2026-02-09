"use client"

import { useEffect, useRef } from "react"

interface WaveformProps {
  className?: string
  barCount?: number
  animate?: boolean
}

export function Waveform({
  className = "",
  barCount = 40,
  animate = false,
}: WaveformProps) {
  const barsRef = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    if (!animate) return

    const intervals: NodeJS.Timeout[] = []

    barsRef.current.forEach((bar, i) => {
      if (!bar) return
      const baseHeight = Math.sin(i * 0.4) * 30 + 35
      const animate = () => {
        const variation = Math.random() * 20 - 10
        bar.style.height = `${Math.max(5, baseHeight + variation)}%`
      }
      animate()
      intervals.push(setInterval(animate, 150 + Math.random() * 200))
    })

    return () => intervals.forEach(clearInterval)
  }, [animate])

  return (
    <div className={`flex items-center gap-[1px] h-8 ${className}`}>
      {Array.from({ length: barCount }).map((_, i) => {
        const staticHeight = Math.sin(i * 0.3) * 35 + 40
        return (
          <div
            key={i}
            ref={(el) => {
              barsRef.current[i] = el
            }}
            className="flex-1 rounded-full transition-all duration-150 ease-out"
            style={{
              height: `${staticHeight}%`,
              backgroundColor: "var(--burnt-peach)",
              opacity: 0.4 + Math.sin(i * 0.2) * 0.3,
            }}
          />
        )
      })}
    </div>
  )
}
