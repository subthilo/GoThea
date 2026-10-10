import io
import os
import base64
from typing import Optional, Union, List, Dict, Any, Generator
from pathlib import Path

from openai import OpenAI
import fitz  # PyMuPDF
from PIL import Image
from dotenv import load_dotenv

# Automatisch .env im Root oder im experiments/ Ordner laden
load_dotenv()
_local_env = Path(__file__).resolve().parent.parent / ".env"
if _local_env.exists():
    load_dotenv(_local_env)


class OpenAISocraticEngine:
    """
    Eigenständiges Modul für OpenAI-Anbindung:
    - Text & Reasoning (GPT-6: luna, sol, astra)
    - Bildgenerierung (Image 2.5: sunburst, flare)
    - Videogenerierung (Sora 2: 4s/8s Cartoon-Clips)
    - Multimodal (PDF, PNG, JPEG, Base64, Bytes)
    - High-DPI & In-Memory Preprocessing (max 2000x2000, Q85)
    - Streaming & Sokratische Didaktik
    """

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self._explicit_key = api_key
        self._client: Optional[OpenAI] = None
        self.default_model = default_model or os.getenv("OPENAI_MODEL", "gpt-6-luna")
        self.default_image_model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst")
        self.default_video_model = os.getenv("OPENAI_VIDEO_MODEL", "sora-2")

    def get_client(self) -> OpenAI:
        """Initialisiert den OpenAI-Client lazy oder aktualisiert ihn bei Key-Wechsel."""
        current_key = self._explicit_key or os.getenv("OPENAI_API_KEY", "")
        if not current_key:
            raise ValueError(
                "Kein OPENAI_API_KEY gefunden! Bitte in .env eintragen oder als Umgebungsvariable setzen."
            )

        if self._client is None or self._client.api_key != current_key:
            self._client = OpenAI(api_key=current_key)
        return self._client

    @staticmethod
    def process_image_to_base64(image_input: Union[str, Path, bytes, Image.Image]) -> str:
        """Optimiert ein Bild im Arbeitsspeicher: Max 2000x2000, JPEG Q85, Base64."""
        if isinstance(image_input, (str, Path)):
            path_str = str(image_input)
            if not os.path.exists(path_str):
                raise FileNotFoundError(f"Bilddatei nicht gefunden: {path_str}")
            img = Image.open(path_str)
        elif isinstance(image_input, bytes):
            img = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, Image.Image):
            img = image_input
        else:
            raise TypeError(f"Nicht unterstützter Bildtyp: {type(image_input)}")

        if img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail((2000, 2000))
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    @classmethod
    def pdf_to_image_base64_list(cls, pdf_path: Union[str, Path], max_pages: int = 5) -> List[str]:
        """Rendert PDF-Seiten mit 300 DPI und optimiert sie für Vision-LLM."""
        pdf_path_str = str(pdf_path)
        if not os.path.exists(pdf_path_str):
            raise FileNotFoundError(f"PDF nicht gefunden: {pdf_path_str}")

        base64_images = []
        doc = fitz.open(pdf_path_str)
        try:
            pages_to_render = min(len(doc), max_pages)
            for page_num in range(pages_to_render):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                b64 = cls.process_image_to_base64(img)
                base64_images.append(b64)
        finally:
            doc.close()

        return base64_images

    def send_prompt(
        self,
        prompt_text: str,
        image_or_pdf: Optional[Union[str, Path, bytes, Image.Image]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1500,
        high_detail: bool = True,
    ) -> str:
        """Sendet synchrone Chat-Completion-Anfrage."""
        active_model = model or self.default_model
        messages: List[Dict[str, Any]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content: List[Dict[str, Any]] = [{"type": "text", "text": prompt_text}]

        if image_or_pdf is not None:
            is_pdf = isinstance(image_or_pdf, (str, Path)) and str(image_or_pdf).lower().endswith(".pdf")
            detail_setting = "high" if high_detail else "auto"

            if is_pdf:
                b64_list = self.pdf_to_image_base64_list(image_or_pdf)
                for b64 in b64_list:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}",
                            "detail": detail_setting,
                        },
                    })
            else:
                if isinstance(image_or_pdf, str) and image_or_pdf.startswith("data:image"):
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": image_or_pdf,
                            "detail": detail_setting,
                        },
                    })
                else:
                    b64 = self.process_image_to_base64(image_or_pdf)
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}",
                            "detail": detail_setting,
                        },
                    })

        messages.append({"role": "user", "content": user_content})

        kwargs: Dict[str, Any] = {
            "model": active_model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }
        if "gpt-6" not in active_model and not active_model.startswith("o"):
            kwargs["temperature"] = temperature

        client = self.get_client()
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def stream_prompt(
        self,
        prompt_text: str,
        image_or_pdf: Optional[Union[str, Path, bytes, Image.Image]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> Generator[str, None, None]:
        """Streaming-Variante für sofortige Audio-/Textausgabe Chunks."""
        active_model = model or self.default_model
        messages: List[Dict[str, Any]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content: List[Dict[str, Any]] = [{"type": "text", "text": prompt_text}]

        if image_or_pdf is not None:
            b64 = self.process_image_to_base64(image_or_pdf)
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                    "detail": "high",
                },
            })

        messages.append({"role": "user", "content": user_content})

        kwargs: Dict[str, Any] = {
            "model": active_model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
            "stream": True,
        }
        if "gpt-6" not in active_model and not active_model.startswith("o"):
            kwargs["temperature"] = temperature

        client = self.get_client()
        stream = client.chat.completions.create(**kwargs)

        for chunk in stream:
            content = chunk.choices[0].delta.content if chunk.choices else None
            if content:
                yield content

    def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: str = "1024x1024",
        save_path: Optional[Union[str, Path]] = None,
    ) -> bytes:
        """Generiert ein Bild mit OpenAI (Standard: gpt-image-2.5-sunburst)."""
        active_model = model or self.default_image_model
        client = self.get_client()

        response = client.images.generate(
            model=active_model,
            prompt=prompt,
            n=1,
            size=size,
        )

        item = response.data[0]
        if item.b64_json:
            image_bytes = base64.b64decode(item.b64_json)
        elif item.url:
            import httpx
            image_bytes = httpx.get(item.url).content
        else:
            raise RuntimeError("Keine Bilddaten von OpenAI erhalten.")

        if save_path:
            p = Path(save_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(image_bytes)

        return image_bytes

    def generate_video(
        self,
        prompt: str,
        model: Optional[str] = None,
        seconds: str = "4",
        size: str = "1280x720",
        save_path: Optional[Union[str, Path]] = None,
    ) -> bytes:
        """
        Generiert ein kurzes Video mit OpenAI Sora 2 (Standard: sora-2, 4 Sekunden).
        Gibt die MP4-Bytes zurück und speichert es optional an `save_path`.
        """
        active_model = model or self.default_video_model
        client = self.get_client()

        # Video-Job anlegen und warten bis fertig
        video = client.videos.create_and_poll(
            model=active_model,
            prompt=prompt,
            seconds=seconds,
            size=size,
        )

        # Video-Bytes herunterladen
        content_stream = client.videos.download_content(video.id)
        video_bytes = content_stream.read()

        if save_path:
            p = Path(save_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(video_bytes)

        return video_bytes
