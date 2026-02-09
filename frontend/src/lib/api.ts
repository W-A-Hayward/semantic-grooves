export interface BackendResult {
  tags: string | null
  artist: string | null
  title: string | null
  score: number | null
  url: string | null
  relevance: number
}

export interface SearchResponse {
  results: BackendResult[]
}

export async function searchAlbums(query: string, topN: number = 20, k: number = 20): Promise<SearchResponse> {
  try {
    const response = await fetch('/api/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query, top_n: topN, k }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: response.statusText }))
      throw new Error(errorData.error || `Search failed: ${response.statusText}`)
    }

    const data = await response.json()
    console.log("Raw API response:", data)
    return data
  } catch (error) {
    console.error("API call error:", error)
    throw error
  }
}

