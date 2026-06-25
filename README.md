# 🌾 Dijital Tarla Günlüğü

Tarlanın "dijital ikizi" — fotoğraf/video kaydı, aktivite günlüğü ve
yerel doküman + web aramasını birleştiren hibrit bir AI asistanı
sunan Streamlit dashboard'u.

## Klasör Şeması

```
dijital-tarla-gunlugu/
├── app.py
├── config.json
├── requirements.txt
├── .gitignore
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── modules/
│   ├── config_loader.py
│   ├── data_scanner.py
│   ├── rag_engine.py
│   ├── web_search.py
│   ├── ai_engine.py
│   ├── media_manager.py
│   └── log_manager.py
├── data/
│   ├── vegetables/
│   └── olives/
├── project_knowledge/
└── logs/
```

## Mimari Kararlar

- **Direct SDK (LangChain değil):** Tek model çağrısı + basit TF-IDF
  retrieval için LangChain'in soyutlama katmanı gereksiz karmaşıklık
  ekler.
- **TF-IDF (vektör DB değil):** scikit-learn ile hafif, hızlı, şeffaf
  arama.
- **Hibrit sorgu:** Önce yerel PDF'ler taranır, sonuç yoksa web
  aramasına geçilir. Kaynak her zaman gösterilir.
- **google-genai SDK:** Google'ın yeni resmi kütüphanesi kullanıldı.

## Kurulum

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run app.py
```

## Model/Sağlayıcı Değiştirme

`config.json` -> `ai.active_provider`: `"gemini"` veya `"openai"`.

## Güvenlik

API anahtarları kodda asla yer almaz, sadece `st.secrets` üzerinden okunur.