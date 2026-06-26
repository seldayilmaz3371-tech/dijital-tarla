"""
app.py
------
Dijital Tarla Günlüğü - Ana Uygulama Girişi
"""

from __future__ import annotations
import os
import io
from datetime import date, datetime
import streamlit as st
from PIL import Image

from modules.config_loader import load_config, get_active_ai_settings, get_active_search_settings
from modules.data_scanner import DataScanner
from modules.rag_engine import RagEngine
from modules.web_search import WebSearchClient
from modules.ai_engine import AIEngine
from modules.media_manager import MediaManager
from modules.log_manager import LogManager

# ======================================================================
# 1) SAYFA YAPILANDIRMASI
# ======================================================================
CONFIG = load_config("config.json")

st.set_page_config(
    page_title=CONFIG["app"]["title"],
    page_icon=CONFIG["app"]["icon"],
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown("""
<style>
    @media (max-width: 640px) {
        .block-container { padding: 1rem 0.6rem 4rem 0.6rem; }
        h1 { font-size: 1.4rem !important; }
    }
</style>
""", unsafe_allow_html=True)

# ======================================================================
# 2) MODÜLLERİN BAŞLATILMASI
# ======================================================================
@st.cache_resource(show_spinner=False)
def get_data_scanner() -> DataScanner:
    return DataScanner(root_dir=CONFIG["data"]["root_dir"], allowed_extensions=CONFIG["data"]["allowed_media_extensions"])

@st.cache_resource(show_spinner="Bilgi tabanı güncelleniyor...")
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
    return AIEngine(**get_active_ai_settings(CONFIG))

def get_web_search_client() -> WebSearchClient:
    return WebSearchClient(**get_active_search_settings(CONFIG))

def get_media_manager() -> MediaManager:
    return MediaManager(root_dir=CONFIG["data"]["root_dir"], filename_pattern=CONFIG["data"]["media_filename_pattern"], allowed_extensions=CONFIG["data"]["allowed_media_extensions"])

def get_log_manager() -> LogManager:
    return LogManager(log_file=CONFIG["data"]["log_file"], columns=CONFIG["log_schema"]["columns"])

scanner = get_data_scanner()
rag_engine = get_rag_engine()
ai_engine = get_ai_engine()
search_client = get_web_search_client()
media_manager = get_media_manager()
log_manager = get_log_manager()

# ======================================================================
# 3) NAVİGASYON VE KALICI BİLGİ KAYNAĞI (Sidebar)
# ======================================================================
st.title(f"{CONFIG['app']['icon']} {CONFIG['app']['title']}")

PAGES = ["📊 Dashboard", "📸 Medya Yükleme", "💬 AI Sohbet", "📋 Aktivite Günlüğü", "⚙️ Ayarlar"]
page = st.sidebar.radio("Menü", PAGES, label_visibility="collapsed")

# Kalıcı Bilgi Tabanı Gösterimi
st.sidebar.divider()
st.sidebar.header("📚 Bilgi Tabanı")
sources = rag_engine.list_indexed_sources()
if sources:
    st.sidebar.success(f"{len(sources)} döküman aktif.")
    with st.sidebar.expander("Dosyaları gör"):
        for s in sources:
            st.caption(f"• {s}")
else:
    st.sidebar.info("`project_knowledge/` klasörü boş.")

if st.sidebar.button("🔄 Veritabanını Tazele"):
    get_rag_engine.clear()
    st.rerun()

# ======================================================================
# SAYFA İÇERİKLERİ
# ======================================================================
crop_folders = scanner.scan()
crop_names = [c.name for c in crop_folders]

if page == "📊 Dashboard":
    st.subheader("Tarla Genel Durumu")
    if not crop_names:
        st.info("Henüz ürün yok.")
    else:
        selected_crop = st.selectbox("Parsel / Ürün seçin", crop_names)
        summary = log_manager.monthly_summary(selected_crop)
        if not summary.empty:
            st.bar_chart(summary.pivot(index="ay", columns="islem_tipi", values="adet").fillna(0))

elif page == "📸 Medya Yükleme":
    with st.form("media_upload_form", clear_on_submit=True):
        crop_choice = st.text_input("Ürün/Parsel adı")
        islem_tipi = st.selectbox("İşlem Tipi", ["gözlem", "gübreleme", "ilaçlama", "sulama", "hasat", "diğer"])
        uploaded_file = st.file_uploader("Medya dosyası", type=["jpg", "jpeg", "png", "mp4"])
        if st.form_submit_button("Kaydet"):
            if uploaded_file and crop_choice:
                # 1. Klasörü oluştur ve dosyayı kaydet
                scanner.ensure_crop_folder(crop_choice)
                saved = media_manager.save(uploaded_file, crop_folder=crop_choice)
                
                # 2. Log (Günlük) kaydını oluştur ve dosyaya yazdır
                yeni_kayit = {
                    "tarih": str(date.today()), 
                    "parsel_tur": crop_choice, 
                    "islem_tipi": islem_tipi, 
                    "medya_dosyasi": saved.filename
                }
                log_manager.append_entry(yeni_kayit)
                
                # 3. Başarı mesajı
                st.success(f"✅ Dosya kaydedildi ve Aktivite Günlüğü'ne başarıyla işlendi!")

elif page == "💬 AI Sohbet":
    st.subheader("Tarım Asistanı")
    
    # --- OTOMATİK PARSEL ANALİZİ MODÜLÜ ---
    with st.expander("📈 Otomatik Parsel Gelişim Analizi", expanded=False):
        st.info("Bu modül, seçtiğiniz parseldeki eski ve yeni kayıtları karşılaştırarak size gelişim raporu sunar.")
        df_logs = log_manager.load()
        
        # DataFrame boş değilse ve medya_dosyasi sütunu varsa filtrele
        if not df_logs.empty and "medya_dosyasi" in df_logs.columns:
            df_media = df_logs[df_logs["medya_dosyasi"].notna() & (df_logs["medya_dosyasi"] != "")]
            
            if not df_media.empty:
                parsel_listesi = df_media["parsel_tur"].unique()
                secilen_analiz_parseli = st.selectbox("Analiz Edilecek Parsel:", parsel_listesi)
                
                if st.button("🔍 Gelişimi Karşılaştır ve Raporla"):
                    parsel_kayitlari = df_media[df_media["parsel_tur"] == secilen_analiz_parseli].sort_values(by="tarih")
                    
                    if len(parsel_kayitlari) < 2:
                        st.warning("⚠️ Karşılaştırma yapabilmek için bu parselde farklı zamanlarda yüklenmiş en az 2 fotoğraf olmalıdır.")
                    else:
                        ilk_kayit = parsel_kayitlari.iloc[0]
                        son_kayit = parsel_kayitlari.iloc[-1]
                        
                        ilk_foto_yolu = os.path.join(CONFIG["data"]["root_dir"], secilen_analiz_parseli, str(ilk_kayit["medya_dosyasi"]))
                        son_foto_yolu = os.path.join(CONFIG["data"]["root_dir"], secilen_analiz_parseli, str(son_kayit["medya_dosyasi"]))
                        
                        if os.path.exists(ilk_foto_yolu) and os.path.exists(son_foto_yolu):
                            with st.spinner("Geçmiş arşiv taranıyor ve analiz ediliyor. Lütfen bekleyin..."):
                                try:
                                    img1 = Image.open(ilk_foto_yolu)
                                    img2 = Image.open(son_foto_yolu)
                                    
                                    hedef_genislik = 800
                                    oran1 = hedef_genislik / float(img1.size[0])
                                    img1 = img1.resize((hedef_genislik, int(float(img1.size[1]) * float(oran1))))
                                    
                                    oran2 = hedef_genislik / float(img2.size[0])
                                    img2 = img2.resize((hedef_genislik, int(float(img2.size[1]) * float(oran2))))
                                    
                                    birlesik_img = Image.new('RGB', (img1.width + img2.width, max(img1.height, img2.height)))
                                    birlesik_img.paste(img1, (0, 0))
                                    birlesik_img.paste(img2, (img1.width, 0))
                                    
                                    img_byte_arr = io.BytesIO()
                                    birlesik_img.save(img_byte_arr, format='JPEG')
                                    image_bytes = img_byte_arr.getvalue()
                                    
                                    analiz_sorusu = (
                                        f"Sen bir Tarım Müfettişisin. Görselde sol tarafta {ilk_kayit['tarih']} tarihli, "
                                        f"sağ tarafta ise {son_kayit['tarih']} tarihli {secilen_analiz_parseli} parseline ait iki fotoğraf yan yana. "
                                        f"Bu iki dönemi kıyaslayarak sadece 3 başlıkta kısa rapor ver:\n"
                                        f"1) Gelişim Seyri (Büyüme/kötüleşme var mı?)\n"
                                        f"2) Sağlık Durumu (Hastalık/zararlı izi belirdi mi?)\n"
                                        f"3) Müdahale Önerisi (Gübre/su tavsiyesi)."
                                    )
                                    
                                    response = ai_engine.analyze_image(image_bytes=image_bytes, mime_type="image/jpeg", question=analiz_sorusu)
                                    st.success("Analiz Tamamlandı!")
                                    st.image(birlesik_img, caption=f"Sol: {ilk_kayit['tarih']} | Sağ: {son_kayit['tarih']}")
                                    st.markdown("### 📊 Otomatik Gelişim Raporu")
                                    st.markdown(response.text)
                                    
                                    if "chat_history" not in st.session_state: st.session_state.chat_history = []
                                    st.session_state.chat_history.append({"role": "assistant", "content": f"**{secilen_analiz_parseli} Karşılaştırma Raporu:**\n\n{response.text}"})
                                    
                                except Exception as e:
                                    st.error(f"Görsel işleme veya AI analizi sırasında hata oluştu: {e}")
                        else:
                            st.error("Dosyalar sistemde bulunamadı. Lütfen Medya Yükleme geçmişinizi kontrol edin.")
            else:
                st.info("Sistemde karşılaştırma yapılacak görsel kayıt bulunamadı.")
        else:
            st.info("Günlükte henüz medya kaydı bulunmuyor.")
    # -----------------------------------------------------------
    
    with st.expander("📸 Fotoğraf Analizi (Manuel Yükleme)", expanded=False):
        uploaded_ai_image = st.file_uploader(
            "Anlık analiz için bir fotoğraf yükleyin (İsteğe bağlı):", 
            type=['png', 'jpg', 'jpeg'],
            key="ai_chat_uploader"
        )
        if uploaded_ai_image is not None:
            st.image(uploaded_ai_image, caption="Yüklendi ve analize hazır", use_container_width=True)

    if "chat_history" not in st.session_state: st.session_state.chat_history = []
    
    for msg in st.session_state.chat_history:
        if msg["role"] in ["user", "assistant"]: 
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
    
    if user_query := st.chat_input("Sorunuzu yazın..."):
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"): st.markdown(user_query)
        
        with st.chat_message("assistant"):
            with st.spinner("Bilgi kaynakları taranıyor ve analiz ediliyor..."):
                rag_results = rag_engine.search(user_query)
                local_context = "\n---\n".join(r.chunk.text for r in rag_results) if rag_results else ""
                
                try:
                    if uploaded_ai_image is not None:
                        image_bytes = uploaded_ai_image.getvalue()
                        mime_type = uploaded_ai_image.type
                        response = ai_engine.analyze_image(image_bytes=image_bytes, mime_type=mime_type, question=user_query)
                    else:
                        response = ai_engine.generate(
                            user_query=user_query, 
                            local_context=local_context, 
                            history=st.session_state.chat_history[:-1]
                        )
                    
                    st.markdown(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    error_msg = str(e).lower()
                    if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                        st.warning("⏳ Yapay zeka servisi şu anda yoğun talep görüyor. Lütfen 10-15 saniye bekleyip tekrar deneyin.")
                    else:
                        st.error(f"Sistemsel bir hata oluştu: {e}")

elif page == "📋 Aktivite Günlüğü":
    df = log_manager.load()
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Değişiklikleri Kaydet"):
        log_manager.save(edited_df)
        st.success("Günlük güncellendi.")

elif page == "⚙️ Ayarlar":
    st.subheader("Sistem Ayarları")
    st.write("API Anahtarları ve yapılandırma bilgileri aktif.")