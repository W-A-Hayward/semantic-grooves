"""The `sg` command line: serve the API, search from the terminal, build the database."""
import argparse
import asyncio
import sys

from . import __version__


def build_parser():
    parser = argparse.ArgumentParser(
        prog="sg", description="Semantic Grooves: discover music by mood.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run the search API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--debug", action="store_true", help="Flask debug mode (auto-reload, never for production)")
    p.add_argument("--static", metavar="DIR", default=None,
                   help="also serve the built frontend from DIR (default: $SG_STATIC_DIR)")
    p.set_defaults(handler=cmd_serve)

    p = sub.add_parser("search", help="search from the terminal")
    p.add_argument("query", nargs="+", help="what you want to hear, e.g. 'warm and unhurried'")
    p.add_argument("-n", "--top-n", type=int, default=10, help="number of albums (default 10)")
    p.add_argument("-k", type=int, default=20, help="RRF constant (default 20)")
    p.set_defaults(handler=cmd_search)

    p = sub.add_parser("fetch-data", help="download the Pitchfork dataset from Kaggle")
    p.add_argument("--dest", help="where to put database.sqlite (default: $SG_DB_PATH or ./database.sqlite)")
    p.add_argument("--force", action="store_true", help="overwrite an existing database")
    p.set_defaults(handler=cmd_fetch_data)

    p = sub.add_parser("prepare-db", help="remove duplicate reviews and add indexes (safe to repeat)")
    p.set_defaults(handler=cmd_prepare_db)

    p = sub.add_parser("build-tags", help="chunk reviews and tag their mood with Ollama (slow)")
    p.add_argument("--model", default=None, help="Ollama model (default qwen2.5:7b)")
    p.add_argument("--batch-size", type=int, default=None, help="reviews tagged concurrently (default 10)")
    p.add_argument("--limit", type=int, default=None, help="stop after N reviews (for trying it out)")
    p.set_defaults(handler=cmd_build_tags)

    p = sub.add_parser("build-index", help="embed chunks and build the vector + full-text indexes")
    p.add_argument("--batch-size", type=int, default=None, help="sentences per model call (default 128)")
    p.add_argument("--rebuild", action="store_true", help="drop the existing indexes and start over")
    p.set_defaults(handler=cmd_build_index)

    return parser


def cmd_serve(args):
    from .api import app, register_frontend
    if args.static:
        try:
            register_frontend(app, args.static)
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


def cmd_search(args):
    from .db import connect
    from .embedding import embed_query
    from .search import search_albums

    query = " ".join(args.query)
    db = connect(read_only=True)
    try:
        results = search_albums(db.cursor(), query, embed_query(query), top_n=args.top_n, k=args.k)
    finally:
        db.close()

    if not results:
        print("No results.")
        return 0
    for rank, r in enumerate(results, start=1):
        print(f"{rank:>2}. {r['artist']} - {r['title']}  (Pitchfork {r['score']}, relevance {r['relevance']})")
        print(f"      {r['tags']}")
    return 0


def cmd_fetch_data(args):
    from .pipeline.dataset import fetch_data
    try:
        fetched = fetch_data(args.dest, force=args.force)
    except (FileExistsError, FileNotFoundError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"Saved {fetched.path}")
    if fetched.duplicates_removed:
        print(f"Removed {fetched.duplicates_removed} duplicate review rows.")
    return 0


def cmd_prepare_db(args):
    from .db import connect
    from .pipeline.prepare import prepare_database

    db = connect()
    try:
        prepared = prepare_database(db)
    finally:
        db.close()
    print(f"Removed {prepared.duplicate_rows} duplicate rows and {prepared.duplicate_chunks} duplicate chunks. "
          "Indexes are in place.")
    return 0


def cmd_build_tags(args):
    from .db import connect
    from .pipeline import tagging

    options = {"limit": args.limit}
    if args.model:
        options["model"] = args.model
    if args.batch_size:
        options["batch_size"] = args.batch_size

    db = connect()
    try:
        result = asyncio.run(tagging.run(db, **options))
    except KeyboardInterrupt:
        print("\nInterrupted. Progress is saved; run the command again to resume.")
        return 130
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()
    message = f"Tagged {result.tagged} reviews."
    if result.failed:
        message += f" {result.failed} got no tags and will be retried on the next run."
    print(message)
    return 0


def cmd_build_index(args):
    from .db import connect
    from .pipeline import indexing

    db = connect()
    try:
        added = indexing.build_index(
            db, batch_size=args.batch_size or indexing.BATCH_SIZE, rebuild=args.rebuild)
    except KeyboardInterrupt:
        print("\nInterrupted. Progress is saved; run the command again to resume.")
        return 130
    finally:
        db.close()
    print(f"Indexed {added} new chunks.")
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
