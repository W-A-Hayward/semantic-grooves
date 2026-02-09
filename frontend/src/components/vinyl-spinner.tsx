"use client"

interface VinylSpinnerProps {
  size?: number
  spinning?: boolean
  className?: string
}

export function VinylSpinner({
  size = 120,
  spinning = true,
  className = "",
}: VinylSpinnerProps) {
  const grooveCount = 8

  return (
    <div
      className={`relative ${className}`}
      style={{ width: size, height: size }}
    >
      <svg
        viewBox="0 0 120 120"
        className={spinning ? "animate-vinyl-spin" : ""}
        style={{ width: size, height: size }}
      >
        {/* Vinyl body */}
        <circle cx="60" cy="60" r="58" fill="#1a1614" stroke="var(--terracotta-clay)" strokeWidth="0.5" />

        {/* Grooves */}
        {Array.from({ length: grooveCount }).map((_, i) => {
          const radius = 18 + i * 5
          return (
            <circle
              key={i}
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke="var(--rosy-taupe)"
              strokeWidth="0.3"
              opacity={0.2 + i * 0.05}
            />
          )
        })}

        {/* Label area */}
        <circle cx="60" cy="60" r="16" fill="var(--terracotta-clay)" />
        <circle cx="60" cy="60" r="14" fill="var(--burnt-peach)" />

        {/* Spindle hole */}
        <circle cx="60" cy="60" r="2.5" fill="#1a1614" />

        {/* Label text */}
        <text
          x="60"
          y="57"
          textAnchor="middle"
          fill="#1a1614"
          fontSize="4"
          fontFamily="monospace"
          fontWeight="bold"
        >
          CRATE
        </text>
        <text
          x="60"
          y="63"
          textAnchor="middle"
          fill="#1a1614"
          fontSize="3"
          fontFamily="monospace"
        >
          SEARCH
        </text>

        {/* Shine effect */}
        <ellipse
          cx="42"
          cy="42"
          rx="25"
          ry="15"
          fill="white"
          opacity="0.03"
          transform="rotate(-30 42 42)"
        />
      </svg>
    </div>
  )
}
