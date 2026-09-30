# Handwriting OCR Comparison & Implementation Patterns

Research from 2026-07-07 — evaluated 8 approaches for handwritten document OCR in a Python/FastAPI parser that already uses Anthropic Claude for LLM field extraction.

## Comparison Table

| Approach | Handwriting Accuracy | Setup Complexity | Cost / 1000 pages | Latency / page | Structured Output | New Dependencies |
|---|---|---|---|---|---|---|
| Tesseract | ❌ Poor (~30-50%) | None (already installed) | Free | ~1s | Raw text only | None |
| Google Cloud Vision | ✅ Excellent | Medium (GCP account, API key) | ~$1.50 | ~2-5s | Text + bounding boxes | `google-cloud-vision` |
| AWS Textract | ✅ Good | Medium (AWS account, IAM) | ~$1.50 | ~2-5s | Key-value pairs + tables | `boto3` |
| Azure Read API | ✅ Excellent | Medium (Azure account) | ~$1.50 | ~2-5s | Structured reading order | `azure-cognitiveservices-vision` |
| TrOCR (HF) | ⚠️ Moderate (neat only) | High (PyTorch + 2GB models) | Free (compute) | 3-10s CPU | Text line by line | `transformers`, `torch` |
| EasyOCR | ⚠️ Moderate | Medium (~100MB models) | Free (compute) | 2-5s CPU | Text + boxes | `easyocr` |
| PaddleOCR | ❌ Weak for handwriting | Medium | Free (compute) | 1-3s | Text + boxes | `paddleocr` |
| **Claude Vision** | ✅ Excellent | **None — already integrated** | ~$3-15 (LLM tokens) | 3-8s | **Full structured JSON** | **None** |

## Why Claude Vision wins when Claude is already in the stack

1. **Already integrated** — same `anthropic.Anthropic` client, same API key, same model
2. **Best handwriting accuracy** — reads cursive, messy, mixed typed/handwritten with near-human accuracy
3. **Two-in-one** — transcribes image AND extracts structured data in one pipeline (two API calls, same model)
4. **Form/table awareness** — reads handwritten line items in tables, returns structured text
5. **No new billing** — no GCP/AWS/Azure accounts, no new API keys
6. **Cost acceptable** — ~$0.003-0.015 per image (token-based). Negligible for MVP volumes.

## Implementation pattern (Claude Vision for handwritten docs)

### Architecture: Two-call pipeline
```
Image → Claude Vision (transcription prompt) → ExtractedSection text
     → existing LLM field extractor → structured IO record JSON
```

The image extractor returns `ExtractedSection` objects (same interface as PDF/DOCX/XLSX extractors). The transcribed text flows through the existing field extraction pipeline unchanged. This keeps extractor/field-extractor separation clean.

### Key code: Claude Vision API call

```python
import base64
from PIL import Image
import io

def _validate_and_resize(data: bytes) -> tuple[bytes, str]:
    """Validate, resize if >4000px, return (image_bytes, mime_type)."""
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Image too large")
    img = Image.open(io.BytesIO(data))
    width, height = img.size
    mime_type = {"PNG": "image/png", "JPEG": "image/jpeg",
                 "WEBP": "image/webp", "TIFF": "image/tiff",
                 "BMP": "image/bmp"}.get((img.format or "").upper(), "image/jpeg")
    if width > 4000 or height > 4000:
        ratio = min(4000 / width, 4000 / height)
        img = img.convert("RGB").resize((int(width * ratio), int(height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        data = buf.getvalue()
        mime_type = "image/jpeg"
    return data, mime_type

def _transcribe_with_claude(data: bytes, mime_type: str, model: str | None = None) -> str:
    """Send image to Claude Vision, return transcribed text."""
    image_b64 = base64.standard_b64encode(data).decode("utf-8")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=model or "claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
                {"type": "text", "text": TRANSCRIPTION_PROMPT},
            ],
        }],
    )
    return "".join(getattr(b, "text", "") for b in response.content if isinstance(getattr(b, "text", None), str))
```

### Transcription prompt (preserves structure)

```
You are a document transcription specialist. Transcribe ALL text from the image:
1. Field labels and values — e.g. "Advertiser: Coca-Cola"
2. Table structure — pipe-delimited markdown rows
3. Line items — each as its own row
4. Monetary values — include currency: $50,000.00
5. Dates — preserve original format
6. Signatures — note [Signature]
7. Checked boxes — [X] for checked, [ ] for unchecked
8. Handwritten annotations — transcribe even if messy
If illegible, write [ILLEGIBLE]. Do NOT interpret or fill missing info.
```

### Section parsing (text → ExtractedSection objects)

After Claude returns transcribed text, parse it into sections:
- Lines starting with `|` → table sections (with `table_data` as `list[list[str]]`)
- Everything else → text sections
- Consecutive `|` lines are grouped into one table section

### Adding model selection to UI

When the system needs to support multiple AI models for extraction:
1. Add `AVAILABLE_MODELS` list in `field_extractor.py` (value + label pairs)
2. Add `GET /models` endpoint to parser service returning the list
3. UI fetches `/models` on mount, populates dropdown, falls back to static list
4. Selected model passed as form field to `/parse/document` and through to regenerate API
5. Model selection persisted to `localStorage` so it survives page reloads
6. Model param threaded through: parser endpoint → `_extract_sections()` → image extractor, and `_build_io_record()` → `extract_io_fields()`
7. Cache key in field extractor includes model to avoid cross-model cache hits