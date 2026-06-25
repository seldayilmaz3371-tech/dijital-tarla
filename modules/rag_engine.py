"""
rag_engine.py
-------------
"Sıfır Varsayım" protokolünün teknik karşılığı: Kullanıcının sorusunu
önce "project_knowledge/" altındaki PDF'lerde arar. Her sonuç, HANGİ
dosyadan geldiğini belirtir (analiz kaynaklılığı). Eşik altı benzerlik
skorlarında "yerel veri yok" sinyali döner ki app.py bunu web aramasına
yönlendirebilsin.

Not: Ağır bir vektör veritabanı (FAISS/Chroma) yerine bilinçli olarak
TF-IDF tabanlı, bağımlılığı az, hızlı ve şeffaf bir retrieval seçildi.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pypdf import PdfReader


@dataclass
class RagChunk:
    text: str
    source_file: str
    page: int


@dataclass
class RagResult:
    chunk: RagChunk
    score: float


class RagEngine:
    def __init__(self, knowledge_dir: str, chunk_size: int = 800,
                 chunk_overlap: int = 150, top_k: int = 4,
                 relevance_threshold: float = 0.12):
        self.knowledge_dir = Path(knowledge_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        self.relevance_threshold = relevance_threshold

        self.chunks: list[RagChunk] = []
        self.vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._index_built = False

    # ------------------------------------------------------------------
    # İndeksleme
    # ------------------------------------------------------------------
    def build_index(self, force: bool = False) -> int:
        """PDF'leri okuyup parçalara ayırır ve TF-IDF indeksini kurar.
        Dönüş: indekslenen parça sayısı."""
        if self._index_built and not force:
            return len(self.chunks)

        self.chunks = []
        pdf_files = sorted(self.knowledge_dir.glob("*.pdf"))

        for pdf_path in pdf_files:
            try:
                reader = PdfReader(str(pdf_path))
            except Exception:
                continue
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                text = re.sub(r"\s+", " ", text).strip()
                if not text:
                    continue
                for chunk_text in self._split_text(text):
                    self.chunks.append(
                        RagChunk(text=chunk_text, source_file=pdf_path.name, page=page_num)
                    )

        if self.chunks:
            self.vectorizer = TfidfVectorizer(max_df=0.9)
            self._matrix = self.vectorizer.fit_transform([c.text for c in self.chunks])
        else:
            self.vectorizer = None
            self._matrix = None

        self._index_built = True
        return len(self.chunks)

    def _split_text(self, text: str) -> list[str]:
        step = max(self.chunk_size - self.chunk_overlap, 1)
        return [
            text[i:i + self.chunk_size]
            for i in range(0, len(text), step)
            if text[i:i + self.chunk_size].strip()
        ]

    # ------------------------------------------------------------------
    # Arama
    # ------------------------------------------------------------------
    def search(self, query: str) -> list[RagResult]:
        """Soruya en alakalı parçaları döner. Eşiğin altındaki sonuçlar elenir."""
        if not self._index_built:
            self.build_index()
        if self.vectorizer is None or not self.chunks:
            return []

        query_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self._matrix).flatten()

        ranked = sorted(zip(self.chunks, sims), key=lambda x: x[1], reverse=True)
        results = [
            RagResult(chunk=c, score=float(s))
            for c, s in ranked[: self.top_k]
            if s >= self.relevance_threshold
        ]
        return results

    def has_local_knowledge(self, query: str) -> bool:
        return len(self.search(query)) > 0

    def list_indexed_sources(self) -> list[str]:
        return sorted({c.source_file for c in self.chunks})