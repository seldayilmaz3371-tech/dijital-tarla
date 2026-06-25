"""
data_scanner.py
----------------
"data/" dizinini dinamik olarak tarar. Yeni bir ürün/parsel klasörü
(örn. data/bugday/) eklendiğinde KOD DEĞİŞİKLİĞİ GEREKMEZ; uygulama
bunu otomatik olarak listeye ekler. Bu, "Sıfır Hard-Code" prensibinin
veri katmanındaki uygulamasıdır.
"""

from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class CropFolder:
    """Tek bir ürün/parsel klasörünü temsil eder (örn. data/vegetables)."""
    name: str
    path: Path
    media_files: list[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def media_count(self) -> int:
        return len(self.media_files)


class DataScanner:
    """data/ kök dizinini tarayıp CropFolder nesneleri üretir."""

    def __init__(self, root_dir: str, allowed_extensions: list[str]):
        self.root_dir = Path(root_dir)
        self.allowed_extensions = {ext.lower() for ext in allowed_extensions}
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def scan(self) -> list[CropFolder]:
        """data/ altındaki her alt klasörü bir CropFolder olarak döner."""
        crops: list[CropFolder] = []
        for entry in sorted(self.root_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                media = self._list_media(entry)
                crops.append(CropFolder(name=entry.name, path=entry, media_files=media))
        return crops

    def _list_media(self, folder: Path) -> list[str]:
        files = []
        for f in sorted(folder.iterdir()):
            if f.is_file() and f.suffix.lower() in self.allowed_extensions:
                files.append(f.name)
        return files

    def get_crop_names(self) -> list[str]:
        return [c.name for c in self.scan()]

    def ensure_crop_folder(self, crop_name: str) -> Path:
        """Kullanıcı yeni bir ürün adı girdiğinde klasörü otomatik oluşturur."""
        safe_name = crop_name.strip().lower().replace(" ", "_")
        path = self.root_dir / safe_name
        path.mkdir(parents=True, exist_ok=True)
        return path