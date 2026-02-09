"use client"

import { useState, useCallback } from "react"
import { mockResults, suggestedQueries, type AlbumResult } from "@/lib/mock-data"
import { SearchBar } from "@/components/search-bar"
import { ResultCard } from "@/components/result-card"
import { VinylSpinner } from "@/components/vinyl-spinner"
import { Waveform } from "@/components/waveform"
import { MarqueeTicker } from "@/components/marquee-ticker"
import { StatsBar } from "@/components/stats-bar"
import { EqualizerBars } from "@/components/equalizer-bars"

export default function Page() {
  const [results, setResults] = useState<AlbumResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [currentQuery, setCurrentQuery] = useState("")

  const handleSearch = useCallback((query: string) => {
    setIsSearching(true)
    setCurrentQuery(query)
    setResults([])
    setHasSearched(false)

    // Simulate API delay
    setTimeout(() => {
      // Shuffle and pick random results to simulate different queries
      const shuffled = [...mockResults].sort(() => Math.random() - 0.5)
      const count = Math.floor(Math.random() * 3) + 5
      setResults(
        shuffled.slice(0, count).map((r, i) => ({
          ...r,
          matchScore: Math.max(0.5, r.matchScore - i * 0.03 + (Math.random() * 0.05 - 0.025)),
        }))
      )
      setIsSearching(false)
      setHasSearched(true)
    }, 1500)
  }, [])

  return (
    <main className="min-h-screen relative overflow-hidden" style={{ backgroundColor: "hsl(12 8% 8%)" }}>
      {/* Background texture - subtle noise */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
          backgroundSize: "200px 200px",
        }}
      />

      {/* Header */}
      <header className="relative z-10">
        <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: "hsl(12 8% 14%)" }}>
          <div className="flex items-center gap-3">
            <EqualizerBars barCount={3} active className="h-4" />
            <span
              className="font-mono text-xs uppercase tracking-[0.4em] font-bold"
              style={{ color: "var(--seashell)" }}
            >
              CrateSearch
            </span>
          </div>
          <div className="flex items-center gap-4">
            <span
              className="font-mono text-[9px] uppercase tracking-wider hidden sm:block"
              style={{ color: "var(--rosy-taupe)" }}
            >
              Pitchfork Review Engine
            </span>
            <div
              className="w-2 h-2 rounded-full animate-pulse"
              style={{ backgroundColor: "var(--burnt-peach)" }}
            />
          </div>
        </div>
        <MarqueeTicker />
      </header>

      {/* Hero / Search Section */}
      <section className={`relative z-10 transition-all duration-700 ease-out ${hasSearched || isSearching ? "pt-10 pb-6" : "pt-24 pb-16"}`}>
        <div className="max-w-4xl mx-auto px-6">
          {/* Title - collapses after search */}
          <div
            className={`text-center transition-all duration-700 overflow-hidden ${hasSearched || isSearching ? "max-h-0 opacity-0 mb-0" : "max-h-60 opacity-100 mb-12"}`}
          >
            <div className="flex justify-center mb-6">
              <VinylSpinner size={80} spinning={isSearching} />
            </div>
            <h1
              className="font-mono text-3xl sm:text-5xl font-bold tracking-tight mb-4 text-balance"
              style={{ color: "var(--seashell)" }}
            >
              dig the crate.
            </h1>
            <p
              className="font-mono text-sm sm:text-base max-w-lg mx-auto leading-relaxed"
              style={{ color: "var(--rosy-taupe)" }}
            >
              Hybrid semantic + lexical search across thousands of Pitchfork album reviews. 
              Describe a sound, a feeling, a moment. {"We'll"} find the records.
            </p>

            {/* Decorative waveform */}
            <div className="max-w-md mx-auto mt-8 opacity-30">
              <Waveform barCount={60} />
            </div>
          </div>

          {/* Compact header after search */}
          {(hasSearched || isSearching) && (
            <div className="flex items-center justify-center gap-3 mb-6 animate-fade-in-up">
              <VinylSpinner size={28} spinning={isSearching} />
              <span
                className="font-mono text-lg font-bold tracking-tight"
                style={{ color: "var(--seashell)" }}
              >
                CrateSearch
              </span>
            </div>
          )}

          {/* Search */}
          <SearchBar
            onSearch={handleSearch}
            isSearching={isSearching}
            suggestedQueries={suggestedQueries}
          />
        </div>
      </section>

      {/* Loading state */}
      {isSearching && (
        <section className="relative z-10 py-12">
          <div className="max-w-3xl mx-auto px-6 text-center">
            <div className="flex justify-center mb-6">
              <VinylSpinner size={100} spinning />
            </div>
            <p
              className="font-mono text-xs uppercase tracking-[0.3em] animate-pulse"
              style={{ color: "var(--rosy-taupe)" }}
            >
              digging through the crates...
            </p>
            <div className="max-w-xs mx-auto mt-4">
              <Waveform barCount={30} animate />
            </div>
          </div>
        </section>
      )}

      {/* Results */}
      {hasSearched && !isSearching && (
        <section className="relative z-10 pb-20">
          <div className="max-w-3xl mx-auto px-6">
            {/* Query echo */}
            <div className="text-center mb-6 animate-fade-in-up">
              <span
                className="font-mono text-[10px] uppercase tracking-[0.3em]"
                style={{ color: "hsl(12 8% 30%)" }}
              >
                results for
              </span>
              <p
                className="font-mono text-sm mt-1 italic"
                style={{ color: "var(--burnt-peach)" }}
              >
                {'"'}{currentQuery}{'"'}
              </p>
            </div>

            <StatsBar resultCount={results.length} visible={hasSearched} />

            {/* Results list */}
            <div className="mt-6 flex flex-col gap-3">
              {results.map((result, i) => (
                <ResultCard key={result.id} result={result} index={i} />
              ))}
            </div>

            {/* Bottom waveform decoration */}
            <div className="mt-12 opacity-20">
              <Waveform barCount={80} />
            </div>

            {/* End marker */}
            <div className="mt-8 text-center">
              <span
                className="font-mono text-[9px] uppercase tracking-[0.4em]"
                style={{ color: "hsl(12 8% 22%)" }}
              >
                {'[  end of side A  ]'}
              </span>
            </div>
          </div>
        </section>
      )}

      {/* Footer */}
      <footer
        className="relative z-10 border-t py-6"
        style={{ borderColor: "hsl(12 8% 14%)" }}
      >
        <div className="max-w-4xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <EqualizerBars barCount={3} active className="h-3" />
            <span
              className="font-mono text-[9px] uppercase tracking-[0.3em]"
              style={{ color: "hsl(12 8% 30%)" }}
            >
              CrateSearch v0.1
            </span>
          </div>
          <span
            className="font-mono text-[9px] uppercase tracking-wider"
            style={{ color: "hsl(12 8% 25%)" }}
          >
            Hybrid Search // Pitchfork Reviews // Semantic + Lexical
          </span>
        </div>
      </footer>
    </main>
  )
}
