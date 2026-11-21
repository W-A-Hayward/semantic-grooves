export interface AlbumResult {
  id: string
  artist: string
  album: string
  score: number
  genre: string
  year: number
  label: string
  reviewer: string
  reviewExcerpt: string
  bestNewMusic: boolean
  coverUrl: string
  matchScore: number // 0-1, how well it matched the query (higher is better)
  matchType: "semantic" | "lexical" | "hybrid"
  url?: string | null // URL to the review
  rrfScore?: number // Raw RRF relevance score (higher is better)
}

export const suggestedQueries = [
  "albums about heartbreak and isolation",
  "experimental electronic with emotional depth",
  "jazz-influenced hip hop masterpieces",
  "dream pop that sounds like nostalgia",
  "protest music disguised as art",
  "folk records made in solitude",
  "guitar records that changed everything",
  "albums that sound like winter",
]
