"""Run from repository root: python -m backend.seed"""
import os
from pathlib import Path

from .database import Database
from .fixtures import seed

if __name__ == "__main__":
    folder = Path(os.environ.get("CONDOR_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
    db = Database(folder)
    seed(db)
    db.engine.dispose()
    print(f"Six demo cases initialized (existing data is preserved): {folder}")
