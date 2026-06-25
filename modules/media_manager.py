"""
media_manager.py
-----------------
Fotoğraf/video yüklemelerini standart isimlendirme kuralına göre
(YYYY-MM-DD_ID_tur.ext) diske kaydeder. Dosya adı şablonu config.json
-> data.media_filename_pattern üzerinden gelir; kod içinde sabit değil.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import uuid


@dataclass
class SavedMedia:
    filename: str
    full_path: Path
    crop_folder: str


class MediaManager:
    def __init__(self, root_dir: str, filename_pattern: str, allowed_extensions: list[str]):
        self.root_dir = Path(root_dir)
        self.filename_pattern = filename_pattern
        self.allowed_extensions = {ext.lower() for ext in allowed_extensions}

    def save(self, uploaded_file, crop_folder: str, record_date: date | None = None,
              record_id: str | None = None) -> SavedMedia:
        ext = Path(uploaded_file.name).suffix.lower()
        if ext not in self.allowed_extensions:
            raise ValueError(
                f"Desteklenmeyen dosya uzantısı: {ext}. "
                f"İzin verilenler: {', '.join(sorted(self.allowed_extensions))}"
            )

        record_date = record_date or date.today()
        record_id = record_id or uuid.uuid4().hex[:6]

        filename = self.filename_pattern.format(
            date=record_date.isoformat(),
            id=record_id,
            tur=crop_folder,
            ext=ext,
        )

        target_dir = self.root_dir / crop_folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename

        with open(target_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        return SavedMedia(filename=filename, full_path=target_path, crop_folder=crop_folder)