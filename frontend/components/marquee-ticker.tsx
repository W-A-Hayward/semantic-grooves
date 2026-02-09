"use client"

const genres = [
  "INDIE ROCK",
  "SHOEGAZE",
  "DREAM POP",
  "HIP-HOP",
  "ELECTRONIC",
  "FOLK",
  "R&B",
  "EXPERIMENTAL",
  "JAZZ",
  "POST-PUNK",
  "AMBIENT",
  "ART POP",
  "NOISE",
  "NEO-SOUL",
  "PSYCHEDELIA",
  "SINGER-SONGWRITER",
]

export function MarqueeTicker() {
  const content = genres.join("  //  ")

  return (
    <div
      className="w-full overflow-hidden py-3 border-y"
      style={{ borderColor: "hsl(12 8% 16%)" }}
    >
      <div className="animate-marquee whitespace-nowrap">
        <span
          className="font-mono text-[10px] uppercase tracking-[0.3em] inline-block"
          style={{ color: "var(--terracotta-clay)", opacity: 0.5 }}
        >
          {content}  //  {content}
        </span>
      </div>
    </div>
  )
}
