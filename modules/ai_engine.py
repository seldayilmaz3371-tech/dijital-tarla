"""
ai_engine.py
------------
Gemini ve OpenAI için TEK bir arayüz sunar (Strategy Pattern).
app.py hangi sağlayıcının aktif olduğunu bilmek zorunda değildir;
sadece AIEngine.generate(...) çağırır. Sağlayıcı değişimi SADECE
config.json -> ai.active_provider alanından yapılır, kod değişmez.

GÜNCELLEME (2026-06): Google'ın YENİ resmi "google-genai" SDK'sı
kullanılıyor. Eski "google-generativeai" kütüphanesi üretici
tarafından kullanımdan kaldırıldığı (deprecated) için bilerek
tercih edilmedi.

GÜNCELLEME 2 (2026-06): API çağrılarına hata yönetimi eklendi.
Gemini/OpenAI sunucuları geçici olarak meşgul olduğunda (503),
kota aşıldığında (429) veya ağ sorunu olduğunda artık uygulama
çökmüyor; kullanıcıya anlaşılır bir mesaj gösteriliyor.

GÜNCELLEME 3 (2026-06): Görsel analiz için ayrı sistem promptu
(SYSTEM_PROMPT_VISION_TR) eklendi — RAG/web kaynak çerçevesi
görsel modda artık kullanılmıyor.

"Sıfır Varsayım" ilkesi burada da geçerlidir: bu sınıf tavsiye ÜRETMEZ,
sadece app.py'den gelen, RAG/web kaynaklarıyla zenginleştirilmiş
prompt'u ilgili LLM API'sine iletir ve yanıtı döner.
"""

from __future__ import annotations
from dataclasses import dataclass


SYSTEM_PROMPT_TR = """Sen bir tarımsal danışman ve Baş Agronomsun. Görevin:
1) Asla tahmin yürütme. Sadece sana verilen "YEREL KAYNAK" ve "WEB KAYNAĞI"
   bilgilerine dayanarak yanıt ver.
2) Gübre, ilaç, bitki türü veya hastalık teşhisi gibi kritik konularda,
   eğer sana yeterli/net veri verilmemişse şunu söyle:
   "Bunu kesin olarak teşhis edemem, daha net bir veri veya yakın çekim gerekiyor."
3) Her tavsiyenin sonunda bilgiyi hangi kaynaktan aldığını belirt
   (örnek: "Kaynak: gubre_rehberi.pdf, sayfa 4" veya "Kaynak: Web araması").
4) Eğer hem yerel kaynakta hem webde bilgi yoksa, bunu açıkça söyle ve
   varsayımda bulunma."""

# Görsel analiz için AYRI bir prompt: SYSTEM_PROMPT_TR'deki "YEREL KAYNAK /
# WEB KAYNAĞI" çerçevesi görsel analizde geçerli değildir (bu modda RAG/web
# araması hiç yapılmaz). Aynı prompt'u kullanmak modelin kafasının
# karışmasına ve konu dışı yanıtlar üretmesine yol açıyordu.
SYSTEM_PROMPT_VISION_TR = """Sen bir tarımsal danışman ve Baş Agronomsun. Sana bir
bitki/tarla fotoğrafı ve bir soru veriliyor.
1) Fotoğrafı dikkatlice incele, soruyu SADECE gördüğün görsel kanıta dayanarak yanıtla.
2) Fotoğraf net değilse, çok uzaktan/karanlık çekilmişse veya teşhis için yeterli
   detay içermiyorsa tahmin yürütme; tam olarak şunu söyle:
   "Bunu kesin olarak teşhis edemem, daha net bir veri veya yakın çekim gerekiyor."
3) Emin olmadığın hiçbir şey söylemeden, sadece gözlemlediğin somut belirtileri
   (yaprak rengi, leke, solma, doku, böcek izi vb.) açıkla.
4) "YEREL KAYNAK" veya "WEB KAYNAĞI" kavramlarından hiç bahsetme; bu yanıt
   tamamen ve doğrudan görsele dayanır."""


@dataclass
class AIResponse:
    text: str
    provider_used: str
    model_used: str
    is_error: bool = False


class AIEngine:
    def __init__(self, provider: str, model: str, api_key: str | None):
        self.provider = provider
        self.model = model
        self.api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate(self, user_query: str, local_context: str = "",
                 web_context: str = "", history: list[dict] | None = None) -> AIResponse:
        if not self.is_configured():
            return AIResponse(
                text=("⚠️ API anahtarı bulunamadı. Lütfen `.streamlit/secrets.toml` "
                      f"dosyasına ilgili anahtarı ekleyin (aktif sağlayıcı: {self.provider})."),
                provider_used=self.provider,
                model_used=self.model,
                is_error=True,
            )

        full_prompt = self._build_prompt(user_query, local_context, web_context)

        try:
            if self.provider == "gemini":
                text = self._call_gemini(full_prompt, history or [])
            elif self.provider == "openai":
                text = self._call_openai(full_prompt, history or [])
            else:
                text = f"Tanımsız AI sağlayıcı: {self.provider}"
            return AIResponse(text=text, provider_used=self.provider, model_used=self.model)
        except Exception as exc:
            return AIResponse(
                text=self._friendly_error_message(exc),
                provider_used=self.provider,
                model_used=self.model,
                is_error=True,
            )

    # ------------------------------------------------------------------
    def _build_prompt(self, user_query: str, local_context: str, web_context: str) -> str:
        parts = [f"KULLANICI SORUSU:\n{user_query}\n"]
        if local_context:
            parts.append(f"YEREL KAYNAK (Project Knowledge):\n{local_context}\n")
        else:
            parts.append("YEREL KAYNAK: Bu soruyla ilgili yerel dokümanlarda eşleşme bulunamadı.\n")
        if web_context:
            parts.append(f"WEB KAYNAĞI (güncel arama sonuçları):\n{web_context}\n")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # HATA YÖNETİMİ
    # ------------------------------------------------------------------
    def _friendly_error_message(self, exc: Exception) -> str:
        """Ham API istisnasını kullanıcının anlayabileceği bir mesaja çevirir."""
        msg = str(exc)

        if "503" in msg or "UNAVAILABLE" in msg or "overloaded" in msg.lower():
            return ("⚠️ Yapay zeka servisi şu anda yüksek talep nedeniyle geçici olarak "
                     "yanıt veremiyor. Lütfen 10-15 saniye bekleyip sorunuzu tekrar gönderin.")

        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "rate limit" in msg.lower() or "quota" in msg.lower():
            return ("⚠️ API kullanım kotanız (dakikalık/günlük limit) doldu. "
                     "Birkaç dakika bekleyip tekrar deneyin, ya da Google AI Studio / "
                     "OpenAI hesabınızdaki kota durumunu kontrol edin.")

        if "404" in msg or "not found" in msg.lower():
            return (f"⚠️ Belirtilen model bulunamadı (`{self.model}`). "
                     "`config.json` dosyasındaki model adının hâlâ geçerli olduğunu kontrol edin "
                     "(modeller zaman zaman üretici tarafından kullanımdan kaldırılabilir).")

        if "401" in msg or "403" in msg or "API key not valid" in msg or "permission" in msg.lower():
            return ("⚠️ API anahtarı geçersiz veya yetkisiz görünüyor. "
                     "`.streamlit/secrets.toml` dosyasındaki anahtarı kontrol edin.")

        if "timeout" in msg.lower() or "connection" in msg.lower():
            return "⚠️ İnternet bağlantısı veya sunucu zaman aşımı sorunu oluştu. Lütfen tekrar deneyin."

        return f"⚠️ AI servisinden yanıt alınırken beklenmeyen bir hata oluştu: {msg[:200]}"

    # ------------------------------------------------------------------
    # GEMINI (yeni google-genai SDK)
    # ------------------------------------------------------------------
    def _call_gemini(self, prompt: str, history: list[dict]) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        chat = client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT_TR),
            history=self._to_gemini_history(history),
        )
        response = chat.send_message(prompt)
        return response.text

    def _to_gemini_history(self, history: list[dict]):
        from google.genai import types
        mapped = []
        for h in history:
            role = "model" if h["role"] == "assistant" else "user"
            mapped.append(types.Content(role=role, parts=[types.Part(text=h["content"])]))
        return mapped

    # ------------------------------------------------------------------
    # OPENAI (değişmedi)
    # ------------------------------------------------------------------
    def _call_openai(self, prompt: str, history: list[dict]) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        messages = [{"role": "system", "content": SYSTEM_PROMPT_TR}]
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(model=self.model, messages=messages)
        return resp.choices[0].message.content

    # ------------------------------------------------------------------
    # GÖRSEL ANALİZ
    # ------------------------------------------------------------------
    def analyze_image(self, image_bytes: bytes, mime_type: str, question: str) -> AIResponse:
        """Yüklenen bitki/hastalık fotoğrafını analiz eder."""
        if not self.is_configured():
            return AIResponse(
                text="⚠️ API anahtarı bulunamadı.",
                provider_used=self.provider, model_used=self.model,
                is_error=True,
            )
        try:
            if self.provider == "gemini":
                text = self._gemini_vision(image_bytes, mime_type, question)
            elif self.provider == "openai":
                text = self._openai_vision(image_bytes, mime_type, question)
            else:
                text = f"Tanımsız AI sağlayıcı: {self.provider}"
            return AIResponse(text=text, provider_used=self.provider, model_used=self.model)
        except Exception as exc:
            return AIResponse(
                text=self._friendly_error_message(exc),
                provider_used=self.provider, model_used=self.model,
                is_error=True,
            )

    def _gemini_vision(self, image_bytes: bytes, mime_type: str, question: str) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                question,
            ],
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT_VISION_TR),
        )
        return response.text

    def _openai_vision(self, image_bytes: bytes, mime_type: str, question: str) -> str:
        import base64
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_VISION_TR},
                {"role": "user", "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                ]},
            ],
        )
        return resp.choices[0].message.content