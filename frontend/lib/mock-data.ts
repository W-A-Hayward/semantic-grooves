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
  matchScore: number // 0-1, how well it matched the query
  matchType: "semantic" | "lexical" | "hybrid"
}

export const mockResults: AlbumResult[] = [
  {
    id: "1",
    artist: "Radiohead",
    album: "Kid A",
    score: 10.0,
    genre: "Electronic / Experimental",
    year: 2000,
    label: "Capitol",
    reviewer: "Brent DiCrescenzo",
    reviewExcerpt:
      "The rock record that reinvented what rock could be. Kid A is a glacier: cold on the surface, but underneath teeming with life, warmth, and a strange, alien beauty that has never been replicated.",
    bestNewMusic: true,
    coverUrl: "",
    matchScore: 0.97,
    matchType: "hybrid",
  },
  {
    id: "2",
    artist: "Bon Iver",
    album: "For Emma, Forever Ago",
    score: 8.1,
    genre: "Folk / Indie",
    year: 2008,
    label: "Jagjaguwar",
    reviewer: "Ryan Dombal",
    reviewExcerpt:
      "A stunning debut born from isolation and heartbreak. Justin Vernon's falsetto cuts through the Wisconsin winter like a warm knife, turning a hunting cabin into a cathedral of grief and redemption.",
    bestNewMusic: true,
    coverUrl: "",
    matchScore: 0.92,
    matchType: "semantic",
  },
  {
    id: "3",
    artist: "Kendrick Lamar",
    album: "To Pimp a Butterfly",
    score: 9.3,
    genre: "Hip-Hop / Jazz",
    year: 2015,
    label: "TDE / Aftermath",
    reviewer: "Matthew Trammell",
    reviewExcerpt:
      "Lamar's jazz-funk-soul odyssey is the most important hip-hop record of its decade. Every bar carries the weight of history, every beat a revolution in miniature. This is protest music elevated to high art.",
    bestNewMusic: true,
    coverUrl: "",
    matchScore: 0.89,
    matchType: "hybrid",
  },
  {
    id: "4",
    artist: "Beach House",
    album: "Depression Cherry",
    score: 8.5,
    genre: "Dream Pop",
    year: 2015,
    label: "Sub Pop",
    reviewer: "Larry Fitzmaurice",
    reviewExcerpt:
      "Beach House have perfected the art of sonic amber: music that traps emotions in a golden haze, preserving feelings of longing and desire in their purest, most beautiful form.",
    bestNewMusic: false,
    coverUrl: "",
    matchScore: 0.85,
    matchType: "lexical",
  },
  {
    id: "5",
    artist: "Arcade Fire",
    album: "Funeral",
    score: 9.7,
    genre: "Indie Rock",
    year: 2004,
    label: "Merge",
    reviewer: "David Moore",
    reviewExcerpt:
      "An album that makes you want to smash things and weep simultaneously. Funeral channels collective grief into communal catharsis, building anthems from the rubble of personal devastation with an urgency rarely matched.",
    bestNewMusic: true,
    coverUrl: "",
    matchScore: 0.82,
    matchType: "semantic",
  },
  {
    id: "6",
    artist: "Frank Ocean",
    album: "Blonde",
    score: 9.0,
    genre: "R&B / Art Pop",
    year: 2016,
    label: "Boys Don't Cry",
    reviewer: "Ryan Dombal",
    reviewExcerpt:
      "Ocean dissolves the boundaries between R&B, psychedelia, and confessional poetry. Blonde is a private universe made public, where every whispered syllable carries the gravity of a secret told in the dark.",
    bestNewMusic: true,
    coverUrl: "",
    matchScore: 0.79,
    matchType: "hybrid",
  },
  {
    id: "7",
    artist: "Sufjan Stevens",
    album: "Carrie & Lowell",
    score: 9.3,
    genre: "Folk / Singer-Songwriter",
    year: 2015,
    label: "Asthmatic Kitty",
    reviewer: "Jeremy Larson",
    reviewExcerpt:
      "Stevens strips everything back to bare nerve endings. The arrangements are skeletal, almost transparent, letting the devastating autobiographical lyrics about his mother's death float unguarded in open air.",
    bestNewMusic: true,
    coverUrl: "",
    matchScore: 0.76,
    matchType: "semantic",
  },
  {
    id: "8",
    artist: "My Bloody Valentine",
    album: "Loveless",
    score: 9.9,
    genre: "Shoegaze",
    year: 1991,
    label: "Creation",
    reviewer: "Mark Richardson",
    reviewExcerpt:
      "The sound of a guitar being bent through a wormhole. Loveless doesn't just define shoegaze; it defines the outer limits of what a guitar-based record can achieve when texture replaces melody as the primary vehicle for emotion.",
    bestNewMusic: true,
    coverUrl: "",
    matchScore: 0.73,
    matchType: "lexical",
  },
]

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
