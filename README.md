# Music Discovery

A semantic search system for music reviews using vector embeddings and SQLite.
The aim of this project is to help users discover new music based on other people's reviews, agnostic of styles or genres.
This project is using a dataset of PitchFork reviews, which can be found on [Kaggle](https://www.kaggle.com/datasets/nolanbconaway/pitchfork-data).

## Overview

This project enables semantic search over music reviews by:
- Embedding reviews into vector space using sentence transformers
- Storing embeddings in SQLite with the `sqlite_vec` extension
- Generating tags for reviews using Ollama models
- Performing k-nearest neighbor search to find similar reviews

## Features

- Vector embeddings of music reviews using `qwen2.5:7b`
- Semantic search with k-NN queries
- AI-generated tags (genres, emotions, instruments) using Ollama
- GPU acceleration support (CUDA/ROCm)

## Usage

### Backend Scripts

- `search_engine/embedder.v2.py` - Generate embeddings and populate the vector table
- `search_engine/search.py` - Perform semantic search queries
- `search_engine/preparedb.v2.py` - Generate tags for reviews using Ollama (async batch processing)

### Web Application

1. **Start the API server:**
   ```bash
   python api.py
   ```
   The API will run on `http://localhost:5000`

2. **Start the frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   The frontend will run on `http://localhost:3000`

The frontend provides an elegant web interface for searching music reviews using natural language queries.

## Requirements

### Backend
- Python 3.x
- SQLite with `sqlite_vec` extension
- Sentence Transformers
- Ollama (for tag generation)
- PyTorch (with CUDA/ROCm support optional)
- Flask and Flask-CORS (see `requirements-api.txt`)

### Frontend
- Node.js 18+ and npm
- React 18+

## Todo

- [x] Embed reviews into vectors and insert into virtual table
- [x] Implement a search function that takes an input and returns the k nearest neighbours
- [x] Add tags for each review using ollama model to improve accuracy
- [ ] Chunk reviews into smaller chunks to further improve accuracy


