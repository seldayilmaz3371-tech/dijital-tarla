"""
log_manager.py
---------------
activity_log.csv dosyasını yönetir. Tarlanın "dijital ikizi" mantığı
burada somutlaşır: her yeni kayıt geçmiş kayıtlarla birlikte tutulur,
böylece üst katman (app.py) her zaman tarihsel karşılaştırma yapabilir
(örn. "Bu ay geçen aya göre kaç ilaçlama yapıldı?").
"""

from __future__ import annotations
from pathlib import Path
from datetime import date
import pandas as pd


class LogManager:
    def __init__(self, log_file: str, columns: list[str]):
        self.log_file = Path(log_file)
        self.columns = columns
        self._ensure_file()

    def _ensure_file(self) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_file.exists():
            pd.DataFrame(columns=self.columns).to_csv(self.log_file, index=False)

    def load(self) -> pd.DataFrame:
        df = pd.read_csv(self.log_file)
        for col in self.columns:
            if col not in df.columns:
                df[col] = None
        if "tarih" in df.columns:
            df["tarih"] = pd.to_datetime(df["tarih"], errors="coerce")
        return df

    def append_entry(self, entry: dict) -> None:
        df = self.load()
        new_row = {col: entry.get(col, "") for col in self.columns}
        new_df = pd.DataFrame([new_row])
        # "tarih" sütununu mevcut df ile AYNI dtype'a (datetime64) çeviriyoruz.
        # Aksi halde concat sonrası sütun object dtype'a düşer; bazı satırlar
        # Timestamp, bazıları düz string olur ve to_csv tutarsız format üretir.
        # Bu da bir sonraki yüklemede bazı satırların NaT'a çevrilip veri
        # kaybına (tarihin CSV'de boş kalmasına) yol açar. Test edilmiş,
        # düzeltilmiş halidir.
        if "tarih" in new_df.columns:
            new_df["tarih"] = pd.to_datetime(new_df["tarih"], errors="coerce")
        df = pd.concat([df, new_df], ignore_index=True)
        df.to_csv(self.log_file, index=False)

    def save(self, df: pd.DataFrame) -> None:
        df = df.copy()
        if "tarih" in df.columns:
            df["tarih"] = pd.to_datetime(df["tarih"], errors="coerce")
        df.to_csv(self.log_file, index=False)

    # ------------------------------------------------------------------
    # Dijital ikiz / tarihsel karşılaştırma yardımcıları
    # ------------------------------------------------------------------
    def filter_by_crop(self, crop_folder: str) -> pd.DataFrame:
        df = self.load()
        if "parsel_tur" not in df.columns:
            return df
        return df[df["parsel_tur"] == crop_folder]

    def monthly_summary(self, crop_folder: str | None = None) -> pd.DataFrame:
        df = self.load()
        if crop_folder:
            df = df[df["parsel_tur"] == crop_folder]
        if df.empty or "tarih" not in df.columns:
            return pd.DataFrame(columns=["ay", "islem_tipi", "adet"])
        df = df.dropna(subset=["tarih"])
        df["ay"] = df["tarih"].dt.to_period("M").astype(str)
        return df.groupby(["ay", "islem_tipi"]).size().reset_index(name="adet")

    def compare_with_previous_period(self, crop_folder: str, current_month: str,
                                       previous_month: str) -> dict:
        """Aynı parsel için iki ayı kıyaslar -> dijital ikiz karşılaştırma çıktısı."""
        summary = self.monthly_summary(crop_folder)
        current = summary[summary["ay"] == current_month]["adet"].sum()
        previous = summary[summary["ay"] == previous_month]["adet"].sum()
        delta = current - previous
        return {
            "current_month": current_month,
            "previous_month": previous_month,
            "current_count": int(current),
            "previous_count": int(previous),
            "delta": int(delta),
        }