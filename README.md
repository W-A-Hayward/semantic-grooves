# Semantic grooves

A semantic search system for music reviews using vector embeddings and SQLite.
The aim of this project is to help users discover new music based on other people's reviews, agnostic of styles or genres.
This project is using a dataset of PitchFork reviews, which can be found on [Kaggle](https://www.kaggle.com/datasets/nolanbconaway/pitchfork-data).

## Overview

This project enables semantic search over music reviews by:
- Embedding reviews into vector space using sentence transformers
- Storing embeddings in SQLite with the `sqlite_vec` extension
- Generating tags for reviews using Ollama models
- Performing hybrid search combining semantic (vector) and lexical (keyword) search
- Using Reciprocal Rank Fusion (RRF) to combine results from both search methods

## Search Algorithm

### Hybrid Search Architecture

The search engine uses a **hybrid approach** that combines two complementary search methods:

1. **Semantic Vector Search**: Uses dense vector embeddings to find reviews that are semantically similar to the query, even if they don't share exact keywords.
2. **Lexical Full-Text Search**: Uses traditional keyword matching (BM25 algorithm) to find reviews containing the exact terms from the query.

### How It Works

#### Step 1: Query Encoding
When a user submits a search query, it's encoded into a 1024-dimensional vector using the `BAAI/bge-large-en-v1.5` sentence transformer model. This embedding captures the semantic meaning of the query.

#### Step 2: Parallel Search Execution
Both search methods run in parallel:

**Vector Search:**
- The query vector is compared against all review embeddings stored in the `reviews_vec` virtual table
- Uses cosine similarity (via `sqlite_vec`) to find the k=50 nearest neighbors
- Results are ranked by distance (lower distance = higher similarity)

**Lexical Search:**
- The query text is searched against the `review_text_fts` FTS5 full-text search table
- Uses BM25 ranking algorithm to score matches
- Searches both tags and review chunks
- Returns top 50 results ranked by relevance score

#### Step 3: Reciprocal Rank Fusion (RRF)
The results from both methods are combined using RRF, which:
- Assigns a score to each result based on its rank in each method: `score = 1.0 / (k + rank + 1)`
- Where `k` is a constant (default: 20) and `rank` is the position in the results (0-indexed)
- Results appearing in both lists get higher combined scores
- Final results are sorted by combined RRF score (ascending - lower scores indicate better matches)

**Why RRF?**
- Combines the strengths of both methods: semantic understanding + keyword precision
- Handles cases where one method might miss relevant results
- Results appearing in both lists are boosted, indicating high confidence matches
- The formula ensures that top-ranked results from either method get significant weight

#### Step 4: Result Retrieval
The top N results (default: 20) are fetched with their metadata:
- AI-generated tags (genres, emotions, instruments)
- Artist and album title
- Pitchfork score
- Review URL
- Relevance score (RRF score)

### Embedding Strategy

Reviews are embedded using a combination of tags and review content:
- Format: `"Tags: {tags}\nReview: {chunk}"`
- This ensures the embedding captures both the structured metadata and the review text
- Embeddings are normalized (L2 normalization) for efficient cosine similarity computation
- Stored as 1024-dimensional float vectors in SQLite

### Review Chunking

Long reviews are split into smaller chunks for better accuracy:
- **Chunk Size**: 1200 characters per chunk
- **Overlap**: 200 characters between chunks (prevents context loss at boundaries)
- Each chunk is processed independently to generate tags
- Tags from all chunks are combined to create a comprehensive tag set
- This approach ensures that long reviews don't lose important details during embedding

### Database Schema

The system uses several key tables:

- **`reviews`**: Original Pitchfork review data (artist, title, score, URL, etc.)
- **`content`**: Review text content
- **`review_tags`**: AI-generated tags and review chunks (created by `preparedb.v2.py`)
- **`reviews_vec`**: Virtual table storing vector embeddings (created by `embedder.v2.py`)
- **`review_text_fts`**: FTS5 virtual table for full-text search (created by `embedder.v2.py`)

## Features

- **Hybrid Search**: Combines semantic vector search and lexical keyword search
- **Reciprocal Rank Fusion**: Intelligently merges results from both search methods
- **Vector Embeddings**: Uses `BAAI/bge-large-en-v1.5` (1024-dimensional embeddings)
- **AI-Generated Tags**: Uses Ollama (`qwen2.5:14b`) to extract genres, emotions, and instruments
- **GPU Acceleration**: Supports CUDA/ROCm for faster embedding generation
- **Modern Web Interface**: React + TypeScript frontend with elegant UI
- **RESTful API**: Flask-based API for easy integration

## Project Structure

```
music-discovery/
├── api.py                          # Flask API server (REST endpoint for search)
├── database.sqlite                 # SQLite database with reviews and embeddings
├── requirements-api.txt            # Python dependencies for API
│
├── search_engine/                  # Core search engine scripts
│   ├── embedder.v2.py             # Generates embeddings and creates vector/FTS tables
│   ├── preparedb.v2.py             # Generates AI tags using Ollama (async batch processing)
│   └── search.py                   # Standalone search script (CLI)
│
├── frontend/                       # React + TypeScript frontend (Vite)
│   ├── src/
│   │   ├── App.tsx                # Main application component
│   │   ├── main.tsx               # React entry point
│   │   ├── globals.css            # Global styles and CSS variables
│   │   ├── components/            # UI components
│   │   │   ├── search-bar.tsx     # Search input component
│   │   │   ├── result-card.tsx    # Individual result display
│   │   │   ├── vinyl-spinner.tsx  # Loading animation
│   │   │   ├── waveform.tsx       # Waveform visualization
│   │   │   ├── equalizer-bars.tsx # Equalizer animation
│   │   │   ├── marquee-ticker.tsx # Marquee text component
│   │   │   ├── stats-bar.tsx      # Search statistics display
│   │   │   ├── score-ring.tsx     # Score visualization
│   │   │   └── ui/                # shadcn/ui component library
│   │   │       └── ...            # 40+ reusable UI components
│   │   ├── hooks/                 # React hooks
│   │   │   ├── use-mobile.tsx     # Mobile detection hook
│   │   │   └── use-toast.ts       # Toast notification hook
│   │   └── lib/
│   │       ├── api.ts             # API client for backend
│   │       ├── mock-data.ts       # Type definitions and mock data
│   │       └── utils.ts            # Utility functions (cn helper)
│   ├── public/                    # Static assets
│   ├── index.html                 # HTML entry point
│   ├── package.json               # Frontend dependencies
│   ├── vite.config.ts             # Vite configuration with API proxy
│   ├── tailwind.config.ts         # Tailwind CSS configuration
│   ├── tsconfig.json              # TypeScript configuration
│   ├── postcss.config.mjs         # PostCSS configuration
│   └── components.json            # shadcn/ui configuration
│
├── v1/                            # Legacy scripts (deprecated)
│   ├── embedder.py
│   └── preparedb.py
└── .gitignore                     # Git ignore rules
```

### Data Flow

1. **Data Preparation** (`preparedb.v2.py`):
   - Reads raw review data from database
   - Uses Ollama (qwen2.5:14b) to generate tags for each review
   - Tags include: genres, emotions, instruments, and a summary
   - Stores tags in `review_tags` table
   - Processes reviews in async batches for efficiency

2. **Embedding Generation** (`embedder.v2.py`):
   - Reads tagged reviews from `review_tags`
   - Generates embeddings using BGE-large model (1024 dimensions)
   - Combines tags and review chunks: `"Tags: {tags}\nReview: {chunk}"`
   - Stores embeddings in `reviews_vec` virtual table
   - Creates FTS5 index in `review_text_fts` for lexical search
   - Processes in batches optimized for GPU memory

3. **Search Execution** (`api.py` or `search.py`):
   - User query is encoded to vector
   - Parallel execution of vector and lexical search
   - Results combined via RRF
   - Top results returned with metadata

4. **Frontend Display** (`frontend/src/App.tsx`):
   - Sends search query to API via `/api/search` endpoint
   - Displays results in a responsive 2-column grid layout
   - Shows relevance scores (RRF scores), tags, and review metadata
   - Provides clickable links to original Pitchfork reviews

## Usage

### Initial Setup

1. **Prepare the database:**
   ```bash
   # Generate AI tags for reviews (this may take a while)
   python search_engine/preparedb.v2.py
   ```

2. **Generate embeddings:**
   ```bash
   # Create vector embeddings and FTS index
   python search_engine/embedder.v2.py
   ```

### Running the Application

1. **Start the API server:**
   ```bash
   python api.py
   ```
   The API will run on `http://localhost:5000`

2. **Start the frontend:**
   ```bash
   cd frontend
   npm install  # First time only
   npm run dev
   ```
   The frontend will run on `http://localhost:3000`

### CLI Search (Alternative)

You can also use the standalone search script:
```bash
python search_engine/search.py
```
This will prompt for a query and display results in the terminal.

## Requirements

### Backend
- **Python 3.x** (3.8+)
- **SQLite** with `sqlite_vec` extension (for vector storage)
- **Sentence Transformers** (for embedding generation)
- **Ollama** (for AI tag generation) - requires `qwen2.5:14b` model
- **PyTorch** (with CUDA/ROCm support optional but recommended)
- **Flask and Flask-CORS** (see `requirements-api.txt`)

### Frontend
- **Node.js 18+** and npm
- **React 19+**
- **TypeScript 5.7+**
- **Vite** (build tool)

### Hardware Recommendations
- **GPU**: Recommended for embedding generation (CUDA or ROCm compatible)
- **RAM**: 8GB+ recommended
- **Storage**: ~2GB for database and models

## Performance Considerations

### Search Performance
- **Vector Search**: O(n) where n is the number of reviews, but optimized with approximate nearest neighbor search
- **Lexical Search**: Uses FTS5 index for fast keyword matching
- **RRF Combination**: O(m log m) where m is the number of unique results (typically < 100)
- Typical search latency: < 500ms for databases with 10k+ reviews

### Embedding Generation
- Batch processing optimizes GPU utilization
- Default batch size: 128 (adjustable based on GPU memory)
- Processing time: ~1-2 seconds per 100 reviews on modern GPU

### Tag Generation
- Async batch processing with configurable batch size (default: 10)
- Ollama model inference time depends on hardware
- Can be parallelized across multiple GPU instances

## Technical Details

### Models Used
- **Embedding Model**: `BAAI/bge-large-en-v1.5` (1024 dimensions)
  - State-of-the-art for semantic search
  - Optimized for retrieval tasks
  - Supports GPU acceleration

- **Tag Generation Model**: `qwen2.5:14b` (via Ollama)
  - Large language model for understanding review content
  - Generates structured tags from unstructured text
  - Temperature set to 0 for consistent outputs

### SQLite Extensions
- **sqlite_vec**: Enables vector similarity search directly in SQLite
  - Uses approximate nearest neighbor algorithms
  - Efficient storage and retrieval of high-dimensional vectors
  - Supports cosine similarity and L2 distance

- **FTS5**: Full-text search extension
  - BM25 ranking algorithm
  - Fast keyword matching
  - Supports phrase queries and boolean operators
