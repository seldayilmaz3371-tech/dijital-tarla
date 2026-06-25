"""
app.py
------
Dijital Tarla Günlüğü - Ana Uygulama Girişi

Mimari notu: Bu dosya sadece "orkestrasyon" yapar (sayfa yönlendirme,
UI bileşenleri). İş mantığının tamamı modules/ altındaki sınıflarda
yaşar. Böylece yeni bir sayfa/özellik eklemek için bu dosyayı şişirmek
yerine ilgili modülü genişletmek yeterli olur (Scalable mimari).
"""

from __future__ import annotations
from datetime import date, datetime

import streamlit as st
from pypdf import PdfReader  # YENİ EKLENEN PDF KÜTÜPHANESİ

from modules.config_loader import load_config, get_active_ai_settings, get_active_search_settings
from modules.data_scanner import DataScanner
from modules.rag_engine import RagEngine
from modules.web_search import WebSearchClient
from modules.ai_engine import AIEngine
from modules.media_manager import MediaManager
from modules.log_manager import LogManager


# ======================================================================
# 1) SAYFA YAPILANDIRMASI (Mobil-öncelikli, responsive)
# ======================================================================
CONFIG = load_config("config.json")

st.set_page_config(
    page_title=CONFIG["app"]["title"],
    page_icon=CONFIG["app"]["icon"],
    layout="wide",
    initial_sidebar_state="auto",
)

# Mobilde gereksiz boşlukları azaltan / dokunmatik dostu hafif CSS.
# NOT: Bu sadece görsel ince ayardır, Streamlit'in kendi responsive
# grid sistemini (st.columns) ezmez.
st.markdown("""
<style>
    @media (max-width: 640px) {
        .block-container { padding: 1rem 0.6rem 4rem 0.6rem; }
        h1 { font-size: 1.4rem !important; }
        h2 { font-size: 1.15rem !important; }
        [data-testid="stChatInput"] textarea { font-size: 0.95rem; }
    }
    .block-container { padding-top: 1.2rem; }
</style>
""", unsafe_allow_html=True)


# ======================================================================
# 2) MODÜLLERİN BAŞLATILMASI (cache_resource: maliyetli işlemler tek sefer)
# ======================================================================
@st.cache_resource(show_spinner=False)
def get_data_scanner() -> DataScanner:
    return DataScanner(
        root_dir=CONFIG["data"]["root_dir"],
        allowed_extensions=CONFIG["data"]["allowed_media_extensions"],
    )


@st.cache_resource(show_spinner="Yerel dokümanlar (Project Knowledge) indeksleniyor...")
def get_rag_engine() -> RagEngine:
    rag_cfg = CONFIG["rag"]
    engine = RagEngine(
        knowledge_dir=rag_cfg["knowledge_dir"],
        chunk_size=rag_cfg["chunk_size"],
        chunk_overlap=rag_cfg["chunk_overlap"],
        top_k=rag_cfg["top_k"],
        relevance_threshold=rag_cfg["relevance_threshold"],
    )
    engine.build_index()
    return engine


def get_ai_engine() -> AIEngine:
    ai_settings = get_active_ai_settings(CONFIG)
    return AIEngine(**ai_settings)


def get_web_search_client() -> WebSearchClient:
    search_settings = get_active_search_settings(CONFIG)
    return WebSearchClient(**search_settings)


def get_media_manager() -> MediaManager:
    return MediaManager(
        root_dir=CONFIG["data"]["root_dir"],
        filename_pattern=CONFIG["data"]["media_filename_pattern"],
        allowed_extensions=CONFIG["data"]["allowed_media_extensions"],
    )


def get_log_manager() -> LogManager:
    return LogManager(
        log_file=CONFIG["data"]["log_file"],
        columns=CONFIG["log_schema"]["columns"],
    )


scanner = get_data_scanner()
rag_engine = get_rag_engine()
ai_engine = get_ai_engine()
search_client = get_web_search_client()
media_manager = get_media_manager()
log_manager = get_log_manager()


# ======================================================================
# 3) NAVİGASYON VE BİLGİ KAYNAĞI YÜKLEME (Sidebar)
# ======================================================================
st.title(f"{CONFIG['app']['icon']} {CONFIG['app']['title']}")

PAGES = ["📊 Dashboard", "📸 Medya Yükleme", "💬 AI Sohbet", "📋 Aktivite Günlüğü", "⚙️ Ayarlar"]
page = st.sidebar.radio("Menü", PAGES, label_visibility="collapsed")

crop_folders = scanner.scan()
crop_names = [c.name for c in crop_folders]

# --- YENİ EKLENEN PDF BİLGİ KAYNAĞI YÜKLEME (SIDEBAR) ---
st.sidebar.divider()
st.sidebar.header("📚 Bilgi Kaynağı")
st.sidebar.caption("Tarım rehberleri vb. PDF belgelerinizi buraya yükleyip AI asistanınıza okutun.")
pdf_file = st.sidebar.file_uploader("PDF Yükle", type=["pdf"])

if pdf_file:
    with st.sidebar.status("PDF okunuyor...", expanded=True) as status:
        try:
            reader = PdfReader(pdf_file)
            text = ""
            for page_num in range(len(reader.pages)):
                page_text = reader.pages[page_num].extract_text()
                if page_text:
                    text += page_text + "\n"
            
            # AI'ın hatırlaması için metni session_state (geçici hafıza) içine alıyoruz
            st.session_state.pdf_icerik = text
            st.session_state.pdf_name = pdf_file.name
            status.update(label=f"{pdf_file.name} başarıyla hafızaya alındı!", state="complete", expanded=False)
        except Exception as e:
            status.update(label="PDF okuma hatası!", state="error", expanded=False)
            st.sidebar.error(str(e))
else:
    # Eğer kullanıcı dosyanın yanındaki Çarpı (X) tuşuna basıp dosyayı silerse, hafızayı temizle
    if "pdf_icerik" in st.session_state:
        del st.session_state["pdf_icerik"]
    if "pdf_name" in st.session_state:
        del st.session_state["pdf_name"]


# ======================================================================
# SAYFA: DASHBOARD
# ======================================================================
if page == "📊 Dashboard":
    st.subheader("Tarla Genel Durumu")

    if not crop_names:
        st.info("Henüz `data/` altında bir ürün klasörü yok. "
                 "'Medya Yükleme' sayfasından yeni bir parsel/ürün ekleyebilirsiniz.")
    else:
        cols = st.columns(min(len(crop_names), 3) or 1)
        for i, crop in enumerate(crop_folders):
            with cols[i % len(cols)]:
                st.metric(label=crop.display_name, value=f"{crop.media_count} medya")

        st.divider()
        st.subheader("Tarihsel Karşılaştırma (Dijital İkiz)")
        selected_crop = st.selectbox("Parsel / Ürün seçin", crop_names)
        summary = log_manager.monthly_summary(selected_crop)

        if summary.empty:
            st.caption("Bu parsel için henüz aktivite günlüğü kaydı yok.")
        else:
            pivot = summary.pivot(index="ay", columns="islem_tipi", values="adet").fillna(0)
            st.bar_chart(pivot)

            available_months = sorted(summary["ay"].unique())
            if len(available_months) >= 2:
                c1, c2 = st.columns(2)
                with c1:
                    prev_m = st.selectbox("Önceki ay", available_months, index=len(available_months) - 2)
                with c2:
                    curr_m = st.selectbox("Güncel ay", available_months, index=len(available_months) - 1)
                comp = log_manager.compare_with_previous_period(selected_crop, curr_m, prev_m)
                delta = comp["delta"]
                st.metric(
                    label=f"{curr_m} toplam işlem (vs {prev_m})",
                    value=comp["current_count"],
                    delta=delta,
                )


# ======================================================================
# SAYFA: MEDYA YÜKLEME
# ======================================================================
elif page == "📸 Medya Yükleme":
    st.subheader("Fotoğraf / Video Yükle")
    st.caption("Dosyalar otomatik olarak `YYYY-MM-DD_ID_tür.ext` formatında adlandırılıp ilgili klasöre kaydedilir.")

    with st.form("media_upload_form", clear_on_submit=True):
        new_or_existing = st.radio("Parsel/Ürün", ["Mevcut listeden seç", "Yeni ekle"], horizontal=True)
        if new_or_existing == "Mevcut listeden seç" and crop_names:
            crop_choice = st.selectbox("Ürün/Parsel klasörü", crop_names)
        else:
            crop_choice = st.text_input("Yeni ürün/parsel adı (örn: bugday)")

        record_date = st.date_input("Tarih", value=date.today())
        record_id = st.text_input("Kayıt ID (boş bırakılırsa otomatik üretilir)")
        islem_tipi = st.selectbox("İşlem Tipi", ["gözlem", "gübreleme", "ilaçlama", "sulama", "hasat", "diğer"])
        aciklama = st.text_area("Açıklama / Not")
        uploaded_file = st.file_uploader("Medya dosyası", type=["jpg", "jpeg", "png", "heic", "mp4", "mov"])

        submitted = st.form_submit_button("Kaydet", use_container_width=True)

    if submitted:
        if not crop_choice:
            st.error("Lütfen bir ürün/parsel adı belirtin.")
        elif not uploaded_file:
            st.error("Lütfen bir dosya seçin.")
        else:
            crop_folder_name = crop_choice.strip().lower().replace(" ", "_")
            scanner.ensure_crop_folder(crop_folder_name)
            try:
                saved = media_manager.save(
                    uploaded_file, crop_folder=crop_folder_name,
                    record_date=record_date, record_id=record_id or None,
                )
                log_manager.append_entry({
                    "tarih": record_date.isoformat(),
                    "parsel_tur": crop_folder_name,
                    "kayit_id": record_id or saved.filename.split("_")[1],
                    "islem_tipi": islem_tipi,
                    "aciklama": aciklama,
                    "miktar": "",
                    "birim": "",
                    "kullanici_notu": "",
                    "medya_dosyasi": saved.filename,
                })
                st.success(f"Kaydedildi: {saved.full_path}")
                get_data_scanner.clear()
            except ValueError as e:
                st.error(str(e))


# ======================================================================
# SAYFA: AI SOHBET (Hibrit RAG + Web + Yüklenen PDF)
# ======================================================================
elif page == "💬 AI Sohbet":
    ai_settings = get_active_ai_settings(CONFIG)
    search_settings = get_active_search_settings(CONFIG)

    st.subheader("Tarım Asistanı")
    st.caption(
        f"Aktif model: **{ai_settings['provider']} / {ai_settings['model']}** • "
        f"Arama: **{search_settings['provider']}**"
    )
    if not ai_engine.is_configured():
        st.warning("AI API anahtarı bulunamadı. Lütfen 'Ayarlar' sayfasındaki talimatları izleyin.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    with st.expander("📷 Bir fotoğraf hakkında soru sor (örn. hastalık teşhisi)"):
        chat_image = st.file_uploader("Fotoğraf", type=["jpg", "jpeg", "png"], key="chat_image")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_query = st.chat_input("Sorunuzu yazın (örn: 'Zeytinlerde hümik asit nasıl uygulanır?')")

    if user_query:
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            if chat_image is not None:
                # Görsel analiz modu: RAG/web araması yapılmaz. 
                with st.spinner("Görsel analiz ediliyor..."):
                    response = ai_engine.analyze_image(
                        image_bytes=chat_image.getvalue(),
                        mime_type=chat_image.type,
                        question=user_query,
                    )
                st.markdown(response.text)
                if not response.is_error:
                    st.caption("📷 Bu yanıt yalnızca yüklediğiniz görsele dayanılarak üretildi "
                               "(yerel doküman/web kaynağı kullanılmadı).")
            else:
                with st.spinner("Bilgi kaynakları taranıyor..."):
                    rag_results = rag_engine.search(user_query)

                local_context = ""
                sources = []
                
                # 1. Proje içindeki sabit dokümanlar (Varsa)
                if rag_results:
                    local_context = "\n---\n".join(r.chunk.text for r in rag_results)
                    sources = sorted({f"{r.chunk.source_file} (s.{r.chunk.page})" for r in rag_results})

                # 2. YENİ EKLENEN: Kullanıcının yan menüden yüklediği PDF'in içeriği
                if "pdf_icerik" in st.session_state and "pdf_name" in st.session_state:
                    ek_pdf_metni = f"\n\n--- KULLANICI TARAFINDAN YÜKLENEN BELGE: {st.session_state.pdf_name} ---\n{st.session_state.pdf_icerik}"
                    local_context += ek_pdf_metni
                    sources.append(f"📄 Yüklenen Belge: {st.session_state.pdf_name}")

                # 3. Web Araması (Eğer yerel/yüklenen bilgi yoksa)
                web_context = ""
                web_sources = []
                if not rag_results and "pdf_icerik" not in st.session_state and search_client.is_configured():
                    with st.spinner("Yerel veri bulunamadı, web'de aranıyor..."):
                        web_results = search_client.search(user_query)
                    if web_results:
                        web_context = "\n---\n".join(f"{r.title}: {r.snippet}" for r in web_results)
                        web_sources = [r.url for r in web_results if r.url]

                # AI'a soru ve tüm toplanan bağlamı (context) gönderiyoruz
                response = ai_engine.generate(
                    user_query=user_query,
                    local_context=local_context,
                    web_context=web_context,
                    history=st.session_state.chat_history[:-1],
                )

                st.markdown(response.text)

                # Kaynakları kullanıcıya göster
                if sources:
                    st.caption("📄 Referans Alınan Kaynak: " + ", ".join(sources))
                elif web_sources:
                    st.caption("🌐 Web kaynağı: " + ", ".join(web_sources[:3]))
                elif not response.is_error:
                    st.caption("ℹ️ Bu yanıt için ekstra bir doküman/web kaynağı kullanılmadı. "
                               "Modelin kendi bilgi tabanı kullanıldı.")

        st.session_state.chat_history.append({"role": "assistant", "content": response.text})


# ======================================================================
# SAYFA: AKTİVİTE GÜNLÜĞÜ
# ======================================================================
elif page == "📋 Aktivite Günlüğü":
    st.subheader("Aktivite Günlüğü (activity_log.csv)")

    df = log_manager.load()
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    if st.button("💾 Değişiklikleri Kaydet", use_container_width=True):
        log_manager.save(edited_df)
        st.success("Günlük güncellendi.")

    st.download_button(
        "CSV olarak indir",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="activity_log.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ======================================================================
# SAYFA: AYARLAR
# ======================================================================
elif page == "⚙️ Ayarlar":
    st.subheader("Sistem Ayarları")

    ai_settings = get_active_ai_settings(CONFIG)
    search_settings = get_active_search_settings(CONFIG)

    st.markdown("**Aktif AI Sağlayıcı**")
    st.code(f"provider: {ai_settings['provider']}\nmodel: {ai_settings['model']}", language="yaml")
    st.markdown(
        "🔄 Değiştirmek için `config.json` dosyasındaki `ai.active_provider` "
        "değerini `gemini` veya `openai` olarak güncelleyin."
    )

    st.markdown("**Aktif Arama Sağlayıcı**")
    st.code(f"provider: {search_settings['provider']}", language="yaml")

    st.divider()
    st.markdown("**API Anahtarı Durumu**")
    st.write("Gemini:", "✅ Tanımlı" if ai_settings["provider"] == "gemini" and ai_settings["api_key"] else "❌ Eksik / Aktif Değil")
    st.write("OpenAI:", "✅ Tanımlı" if ai_settings["provider"] == "openai" and ai_settings["api_key"] else "❌ Eksik / Aktif Değil")
    st.write("Arama API:", "✅ Tanımlı" if search_settings["api_key"] else "❌ Eksik")

    st.divider()
    st.markdown("**Yerel Bilgi Tabanı (Project Knowledge)**")
    sources = rag_engine.list_indexed_sources()
    if sources:
        st.write(f"{len(sources)} dosya indekslendi:")
        st.write(sources)
    else:
        st.info("`project_knowledge/` klasörüne henüz sabit PDF eklenmemiş.")
    if st.button("🔄 Bilgi tabanını yeniden indeksle"):
        get_rag_engine.clear()
        st.rerun()