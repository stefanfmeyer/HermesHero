# pdf.js + pdf-lib Integration Reference

Session-specific detail from building a full-featured PDF editor at `$HOME/Developer/pdf-edit`.

## Build Errors Encountered and Fixed

### Error 1: `Uint8Array<ArrayBufferLike>` not assignable to `BlobPart`

**Context:** `pdf-lib`'s `save()` returns `Uint8Array`. TypeScript 5.7+ (used by Next.js 15.5) has stricter type checking that rejects `Uint8Array` for `Blob` constructor and `NextResponse` body.

**Hit in 3 places:**

1. `downloadBytes()` in `pdf-lib-utils.ts`:
```typescript
// ❌
const blob = new Blob([bytes], { type: mimeType });
// ✅
const buffer = new ArrayBuffer(bytes.byteLength);
new Uint8Array(buffer).set(bytes);
const blob = new Blob([buffer], { type: mimeType });
```

2. Print handler in `Toolbar.tsx`:
```typescript
// ❌
const blob = new Blob([bytes], { type: "application/pdf" });
// ✅
const buffer = new ArrayBuffer(bytes.byteLength);
new Uint8Array(buffer).set(bytes);
const blob = new Blob([buffer], { type: "application/pdf" });
```

3. API route `/api/merge/route.ts`:
```typescript
// ❌
return new NextResponse(mergedBytes, { ... });
// ✅
const buffer = new ArrayBuffer(mergedBytes.byteLength);
new Uint8Array(buffer).set(mergedBytes);
return new NextResponse(buffer, { ... });
```

### Error 2: `StandardFonts.HelveticaItalic` does not exist

```typescript
// ❌ Property 'HelveticaItalic' does not exist on type 'typeof StandardFonts'
const helvItalicFont = await pdfDoc.embedFont(StandardFonts.HelveticaItalic);

// ✅ Correct enum name:
const helvItalicFont = await pdfDoc.embedFont(StandardFonts.HelveticaOblique);
```

### Error 3: `Set<number>` iteration type error

```typescript
// ❌ Type error under strict TS config
const toDelete = new Set(pageIndices.sort((a, b) => b - a));
for (const idx of toDelete) { pdfDoc.removePage(idx); }

// ✅ Convert to array:
const toDelete = Array.from(new Set(pageIndices.sort((a, b) => b - a)));
for (const idx of toDelete) { pdfDoc.removePage(idx); }
```

### Error 4: `FormData.entries()` type issue in API route

```typescript
// ❌ Property 'entries' does not exist on type 'FormData' (in Next.js 15 route context)
for (const [, value] of formData.entries()) { ... }

// ✅ Use getAll() with field name:
const entries = formData.getAll("files");
for (const value of entries) {
  if (value instanceof File && value.type === "application/pdf") {
    files.push(value);
  }
}
```

### Error 5: Missing state variable for dialog visibility

When building a toolbar with multiple dropdown menus and modal dialogs, ensure every dialog's visibility is tracked by its own boolean state. Don't try to reuse a string state (like `extractRange !== ""`) as a dialog visibility check — it breaks when the user types and clears text.

```typescript
// ❌ Using data state as visibility flag
const [extractRange, setExtractRange] = useState("");
{showExtractRange !== "" && ( <dialog/> )}

// ✅ Separate visibility state
const [showExtractDialog, setShowExtractDialog] = useState(false);
const [extractRange, setExtractRange] = useState("");
{showExtractDialog && ( <dialog/> )}
```

## pdf.js Worker — import.meta.url Pattern

The key insight: `new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url)` works because Next.js 15's webpack bundler resolves `import.meta.url` at build time and bundles the worker file. This is more reliable than trying to set a CDN URL or copy the worker file manually.

```typescript
"use client";
import * as pdfjsLib from "pdfjs-dist";

let workerConfigured = false;

export async function getPdfjs(): Promise<typeof pdfjsLib> {
  if (!workerConfigured) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
      "pdfjs-dist/build/pdf.worker.min.mjs",
      import.meta.url
    ).toString();
    workerConfigured = true;
  }
  return pdfjsLib;
}
```

## Annotation Layer Architecture

### Coordinate Space: 0–1000 Normalized

All annotation positions (x, y, width, height) are stored as values from 0 to 1000. This is the critical design decision — it makes annotations zoom-independent:

```typescript
// Store: x=500, y=300 means center-top of page
// Render at zoom 1.0 (page is 612px wide):
//   pixelX = (500/1000) * 612 = 306px

// Render at zoom 2.0 (page is 1224px wide):
//   pixelX = (500/1000) * 1224 = 612px
// Same relative position!
```

On export to pdf-lib:
```typescript
const { width: pw, height: ph } = page.getSize();
const pdfX = (ann.x / 1000) * pw;
const pdfY = ph - (ann.y / 1000) * ph; // Y-axis flip: PDF bottom-up vs screen top-down
```

### Rendering Different Annotation Types in React

| Type | HTML Element | Key CSS |
|------|-------------|---------|
| Text | `<div>` / `<textarea>` | `color`, `fontSize`, `fontFamily` |
| Sticky note | `<div>` icon + popup | `position: absolute`, z-index |
| Highlight | semi-transparent `<div>` | `background`, `opacity: 0.3` |
| Rectangle | `<div>` | `border`, `borderRadius: 2px` |
| Circle | `<div>` | `border`, `borderRadius: 50%` |
| Line | rotated `<div>` | `transform: rotate(angle)`, `transformOrigin: left` |
| Arrow | rotated `<div>` + arrow head | border trick for arrowhead |
| Freehand | `<svg><path>` | `strokeLinecap: round` |
| Stamp | rotated bordered `<div>` | `transform: rotate(-10deg)` |
| Image | `<img>` | `objectFit: contain` |
| Signature | `<img>` from canvas dataURL | same as image |
| Redaction | solid black `<div>` | `background: #000` |

### Drag/Move Implementation

```typescript
// On annotation mousedown:
setDragState({ id: ann.id, startX: e.clientX, startY: e.clientY, annX: ann.x, annY: ann.y });

// On window mousemove:
const rect = layerRef.current.getBoundingClientRect();
const dx = ((e.clientX - dragState.startX) / rect.width) * 1000;
const dy = ((e.clientY - dragState.startY) / rect.height) * 1000;
editor.updateAnnotation(dragState.id, { x: dragState.annX + dx, y: dragState.annY + dy });
```

## Build Output (Successful)

```
Route (app)                                 Size  First Load JS
┌ ○ /                                     294 kB         397 kB
├ ○ /_not-found                            991 B         104 kB
├ ƒ /api/merge                             126 B         103 kB
└ ƒ /api/split                             126 B         103 kB
```

Warnings (not errors):
- `@next/next/no-img-element` — intentional, using raw `<img>` for thumbnails/signatures
- `react-hooks/exhaustive-deps` — one useEffect with intentionally limited deps

## Package Versions (Verified Working)

```json
{
  "next": "^15.0.3",
  "react": "^19.0.0",
  "react-dom": "^19.0.0",
  "pdfjs-dist": "^4.8.69",
  "pdf-lib": "^1.17.1",
  "tailwindcss": "^4.0.0",
  "@tailwindcss/postcss": "^4.0.0",
  "typescript": "^5.6.3"
}
```

Actual installed: Next.js 15.5.23, React 19.x, TailwindCSS 4.x.