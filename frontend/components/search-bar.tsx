"use client"

import React from "react"

import { Search, Disc3 } from "lucide-react"
import { useState, useRef, useEffect } from "react"

interface SearchBarProps {
  onSearch: (query: string) => void
  isSearching: boolean
  suggestedQueries: string[]
}

export function SearchBar({ onSearch, isSearching, suggestedQueries }: SearchBarProps) {
  const [query, setQuery] = useState("")
  const [isFocused, setIsFocused] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      onSearch(query.trim())
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    setQuery(suggestion)
    onSearch(suggestion)
    inputRef.current?.blur()
  }

  // Typewriter effect for placeholder
  const [placeholderText, setPlaceholderText] = useState("")
  const phrases = [
    "dreamy shoegaze with walls of sound...",
    "hip-hop that sounds like jazz fusion...",
    "sad folk albums from the 2010s...",
    "experimental electronic masterpieces...",
  ]
  const phraseIndex = useRef(0)
  const charIndex = useRef(0)
  const isDeleting = useRef(false)

  useEffect(() => {
    if (isFocused || query) return

    const interval = setInterval(() => {
      const currentPhrase = phrases[phraseIndex.current]

      if (!isDeleting.current) {
        setPlaceholderText(currentPhrase.slice(0, charIndex.current + 1))
        charIndex.current++

        if (charIndex.current === currentPhrase.length) {
          isDeleting.current = true
          clearInterval(interval)
          setTimeout(() => {}, 2000)
        }
      } else {
        setPlaceholderText(currentPhrase.slice(0, charIndex.current - 1))
        charIndex.current--

        if (charIndex.current === 0) {
          isDeleting.current = false
          phraseIndex.current = (phraseIndex.current + 1) % phrases.length
        }
      }
    }, isDeleting.current ? 30 : 70)

    return () => clearInterval(interval)
  }, [isFocused, query])

  return (
    <div className="w-full max-w-3xl mx-auto">
      <form onSubmit={handleSubmit} className="relative group">
        {/* Glow effect */}
        <div
          className="absolute -inset-[1px] rounded-lg opacity-0 group-focus-within:opacity-100 transition-opacity duration-500 blur-sm"
          style={{ background: "var(--burnt-peach)" }}
        />

        <div
          className="relative flex items-center rounded-lg border transition-all duration-300"
          style={{
            backgroundColor: isFocused ? "hsl(12 8% 14%)" : "hsl(12 8% 12%)",
            borderColor: isFocused ? "var(--burnt-peach)" : "hsl(12 8% 20%)",
          }}
        >
          <div className="pl-4 pr-2 flex items-center">
            {isSearching ? (
              <Disc3
                className="animate-vinyl-spin"
                size={20}
                style={{ color: "var(--burnt-peach)" }}
              />
            ) : (
              <Search
                size={20}
                style={{ color: isFocused ? "var(--burnt-peach)" : "var(--rosy-taupe)" }}
                className="transition-colors duration-300"
              />
            )}
          </div>

          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={placeholderText || "search the crate..."}
            className="flex-1 bg-transparent py-4 px-2 font-mono text-sm outline-none placeholder:opacity-40"
            style={{ color: "var(--seashell)", caretColor: "var(--burnt-peach)" }}
          />

          <button
            type="submit"
            disabled={!query.trim() || isSearching}
            className="mr-2 px-4 py-2 rounded font-mono text-xs uppercase tracking-wider transition-all duration-300 disabled:opacity-30"
            style={{
              backgroundColor: query.trim() ? "var(--terracotta-clay)" : "transparent",
              color: query.trim() ? "hsl(12 8% 10%)" : "var(--rosy-taupe)",
            }}
          >
            {isSearching ? "digging..." : "dig"}
          </button>
        </div>
      </form>

      {/* Suggested queries */}
      <div className="mt-4 flex flex-wrap gap-2 justify-center">
        {suggestedQueries.slice(0, 4).map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => handleSuggestionClick(suggestion)}
            className="px-3 py-1.5 rounded-full font-mono text-[11px] border transition-all duration-200 hover:scale-105 active:scale-95"
            style={{
              borderColor: "hsl(12 8% 22%)",
              color: "var(--rosy-taupe)",
              backgroundColor: "hsl(12 8% 12%)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "var(--burnt-peach)"
              e.currentTarget.style.color = "var(--burnt-peach)"
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "hsl(12 8% 22%)"
              e.currentTarget.style.color = "var(--rosy-taupe)"
            }}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  )
}
