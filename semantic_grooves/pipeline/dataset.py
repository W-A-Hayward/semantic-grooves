"""Step 0: fetch the Pitchfork reviews database from Kaggle."""
import shutil
from pathlib import Path

from ..config import db_path

KAGGLE_DATASET = "nolanbconaway/pitchfork-data"


def download_dataset():
    """Download the Kaggle dataset (cached by kagglehub); returns its directory."""
    try:
        import kagglehub
    except ImportError as e:
        raise RuntimeError(
            "kagglehub is not installed. Run: pip install 'semantic-grooves[build]'"
        ) from e
    return Path(kagglehub.dataset_download(KAGGLE_DATASET))


def fetch_data(dest=None, force=False):
    """Copy the dataset's database.sqlite to `dest` (default: config.db_path()).

    Refuses to overwrite an existing file unless `force` is set, because the
    destination may hold hours of generated tags and embeddings.
    """
    dest = Path(dest) if dest else db_path()
    if dest.exists() and not force:
        raise FileExistsError(f"{dest} already exists (use --force to overwrite it)")

    source = download_dataset() / "database.sqlite"
    if not source.exists():
        raise FileNotFoundError(f"database.sqlite not found in the downloaded dataset ({source.parent})")

    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    shutil.copyfile(source, partial)
    partial.replace(dest)
    return dest
