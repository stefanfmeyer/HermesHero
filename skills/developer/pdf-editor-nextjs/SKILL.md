---
name: pdf-editor-nextjs
description: "Build a PDF viewer/editor with Next.js 15 App Router, pdfjs-dist for rendering, and pdf-lib for manipulation. Covers worker setup, canvas rendering, annotation overlay architecture, export flattening, TypeScript pitfalls, and project structure."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [pdf, nextjs, pdfjs, pdf-lib, typescript, app-router]
    related_skills: [nextjs-development-patterns]
---

# PDF Editor with Next.js 15 + pdf.js + pdf-lib

## Overview

Build a fully-featured PDF viewer and editor (Adobe Acrobat Pro class) as a client-side Next.js 15 app. `pdfjs-dist` renders pages to `<canvas>`, annotations live as HTML/SVG overlay, and `pdf-lib` flattens everything on export.

## When to Use

- User asks to build a PDF viewer, PDF editor, or PDF annotation tool with Next.js
- User needs pdf.js (pdfjs-dist) rendering in a React/Next.js app
- User needs pdf-lib manipulation (merge, split, watermark, form fields) in browser
- User wants annotation overlay architecture on top of PDF canvas
- User asks for features like: highlight, sticky notes, stamps, signatures, redaction, watermarks, form fields

## Tech Stack

- **Next.js 15** (App Router, no turbopack — webpack needed for canvas alias)
- **React 19**
- **TypeScript** (strict)
- **TailwindCSS 4** via `@tailwindcss/postcss`
- **pdfjs-dist v4** — PDF rendering to canvas
- **pdf-lib** — PDF manipulation (annotations, merge, split, export)

## Critical Configuration

### 1. pdf.js Worker Setup (pdfjs-dist v4)

The worker must be configured before any `getDocument()` call. Use `import.meta.url` resolution:

```typescript
// src/lib/pdfjs.ts
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

export async function loadPdf(data: ArrayBuffer) {
  const pdfjs = await getPdfjs();
  return pdfjs.getDocument({ data }).promise;
}
```

**Key points:**
- `import.meta.url` works in Next.js 15's webpack bundler for resolving the worker path
- Use the `.mjs` worker entry point for pdfjs-dist v4 (NOT `.js`)
- `"use client"` directive is required — pdf.js uses browser APIs (Worker, Canvas)
- Guard the init with a `workerConfigured` boolean so it only runs once

### 2. next.config.mjs — Disable Node Canvas

pdf-lib tries to load Node's `canvas` module at import time. Without this alias, the browser build breaks:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    config.resolve.alias.canvas = false;
    return config;
  },
};

export default nextConfig;
```

**Do NOT use `--turbopack`** when you need this webpack alias — turbopack doesn't support `config.resolve.alias` the same way.

### 3. Port Configuration

When standard ports are in use, set custom port in `package.json` scripts:

```json
{
  "scripts": {
    "dev": "next dev -p 3002",
    "build": "next build",
    "start": "next start -p 3002"
  }
}
```

### 4. TailwindCSS 4 Setup (No tailwind.config.js)

Tailwind v4 uses CSS-based config and `@tailwindcss/postcss`:

```javascript
// postcss.config.mjs
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
export default config;
```

```css
/* globals.css */
@import "tailwindcss";

:root {
  --bg-primary: #1e1e1e;
  /* ... */
}
```

## Rendering a Page to Canvas

```typescript
export async function renderPageToCanvas(
  pdfDocument: PDFDocumentProxy,
  pageIndex: number,  // 0-indexed (pdf.js uses 1-indexed internally)
  canvas: HTMLCanvasElement,
  scale: number,
  rotation: number = 0
): Promise<{ width: number; height: number }> {
  const page = await pdfDocument.getPage(pageIndex + 1); // 1-indexed!
  const viewport = page.getViewport({ scale, rotation });
  const ctx = canvas.getContext("2d")!;
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  await page.render({ canvasContext: ctx, viewport }).promise;
  return { width: viewport.width, height: viewport.height };
}
```

## Annotation Overlay Architecture

### Coordinate System

Store annotation positions in a **normalized 0–1000 coordinate space** (both X and Y). This makes annotations resolution-independent:

- **Render to pixels:** `px = (ann.x / 1000) * pageWidth`
- **Export to PDF points:** `pdfX = (ann.x / 1000) * page.getSize().width`
- **Y-axis flip** (PDF is bottom-up, screen is top-down): `pdfY = pageHeight - (ann.y / 1000) * pageHeight`

### Layer Structure

```
<div class="page-container" style="width: pageWidth; height: pageHeight">
  <canvas class="pdf-canvas" />              <!-- pdf.js render -->
  <div class="annotation-layer" />           <!-- HTML/SVG overlay -->
</div>
```

The annotation layer is `position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: auto;` on top of the canvas.

### State Management

All state via a central React hook (no external state lib needed):

```typescript
// usePdfEditor.ts — central hook returning:
{
  pdfDocument, numPages, currentPage, zoom, rotation,
  annotations, selectedAnnotationId, activeTool, displayMode,
  thumbnails, searchResults, savedSignatures,
  properties: { color, strokeWidth, opacity, fontSize, fontFamily },
  actions: { loadFile, addAnnotation, updateAnnotation, deleteAnnotation,
             deletePage, addBlankPage, rotatePage, reorderPages,
             handleSearch, saveSignature, saveProgress, ... }
}
```

### Display Modes

- **Single page:** One canvas, re-render on page/zoom change
- **Continuous scroll:** Render all pages in a scrollable column; use IntersectionObserver or scroll-based visible-page tracking
- **Two-page view:** Render left+right pages side by side; odd/even page alignment

## Export — Flattening Annotations with pdf-lib

```typescript
import { PDFDocument, rgb, StandardFonts, degrees } from "pdf-lib";

export async function savePdfWithAnnotations(
  originalData: ArrayBuffer,
  annotations: Annotation[],
  pageRotations: number[],
  password?: string
): Promise<Uint8Array> {
  const pdfDoc = await PDFDocument.load(originalData, { ignoreEncryption: true });
  const pages = pdfDoc.getPages();
  const helvFont = await pdfDoc.embedFont(StandardFonts.Helvetica);
  // ... embed other fonts as needed

  for (const ann of annotations) {
    const page = pages[ann.pageIndex];
    if (!page) continue;
    const { width: pw, height: ph } = page.getSize();
    const pdfX = (ann.x / 1000) * pw;
    const pdfY = ph - (ann.y / 1000) * ph;

    // Render each annotation type to pdf-lib drawing calls
    switch (ann.type) {
      case "text":
        page.drawText(ann.text, { x: pdfX, y: pdfY - fontSize, size: fontSize, font, color });
        break;
      case "rectangle":
        page.drawRectangle({ x: pdfX, y: pdfY - h, width: w, height: h, borderColor, borderWidth });
        break;
      // ... etc
    }
  }

  const options: any = {};
  if (password) { options.userPassword = password; options.ownerPassword = password; }
  return pdfDoc.save(options);
}
```

## TypeScript Pitfalls (TS 5.6+/5.7+)

These errors are very likely when building a PDF editor with Next.js 15 and TS 5.7+.

### 1. `Uint8Array<ArrayBufferLike>` not assignable to `BlobPart`

`pdf-lib.save()` returns `Uint8Array`. TS 5.7+ rejects it for `Blob` or `NextResponse` because `SharedArrayBuffer` is in the union type.

```typescript
// ❌ Fails:
const blob = new Blob([bytes], { type: "application/pdf" });

// ✅ Fix — copy into a fresh ArrayBuffer:
const buffer = new ArrayBuffer(bytes.byteLength);
new Uint8Array(buffer).set(bytes);
const blob = new Blob([buffer], { type: "application/pdf" });
```

**This hits every place you create a Blob or NextResponse from pdf-lib output:**
- `downloadBytes()` utility
- Print handler (`new Blob` → `URL.createObjectURL` → `window.open`)
- API route responses (`new NextResponse(buffer, ...)`)

### 2. `StandardFonts.HelveticaItalic` does not exist

```typescript
// ❌ TypeScript error
await pdfDoc.embedFont(StandardFonts.HelveticaItalic);

// ✅ Correct name:
await pdfDoc.embedFont(StandardFonts.HelveticaOblique);
```

### 3. `Set` iteration requires `--downlevelIteration` or target es2015+

```typescript
// ❌ May error under certain tsconfig targets
const toDelete = new Set(pageIndices);
for (const idx of toDelete) { ... }

// ✅ Convert to array first:
const toDelete = Array.from(new Set(pageIndices));
for (const idx of toDelete) { ... }
```

### 4. API Route `FormData` iteration type issues

```typescript
// ❌ `formData.entries()` type issues in Next.js 15
for (const [, value] of formData.entries()) { ... }

// ✅ Use getAll() with a field name:
const entries = formData.getAll("files");
for (const value of entries) { ... }
```

### 5. Base64 encoding of `Uint8Array` in API routes

```typescript
// ✅ Manual byte-by-byte encoding (avoids type issues):
let binary = "";
for (let i = 0; i < splitBytes.length; i++) {
  binary += String.fromCharCode(splitBytes[i]);
}
const base64 = btoa(binary);
```

## Project Structure

```
src/
├── app/
│   ├── layout.tsx           # Root layout (html/body only)
│   ├── page.tsx             # Main page (renders PdfEditor)
│   ├── globals.css          # CSS variables + dark theme
│   └── api/
│       ├── merge/route.ts   # POST: merge multiple PDFs
│       └── split/route.ts  # POST: split PDF by page ranges
├── components/
│   ├── PdfEditor.tsx        # Main container + keyboard shortcuts
│   ├── Toolbar.tsx          # Top toolbar (file/pages/edit/forms/security/zoom/search)
│   ├── Sidebar.tsx          # Left (thumbnails/annotations list/bookmarks)
│   ├── PdfViewer.tsx        # Canvas rendering + display modes
│   ├── AnnotationLayer.tsx  # HTML/SVG overlay (render + drag + edit)
│   ├── ToolPalette.tsx     # Floating annotation tool buttons + signature pad
│   ├── PropertiesPanel.tsx  # Right sidebar (annotation properties editor)
│   ├── StatusBar.tsx        # Bottom bar (page info, zoom, tool)
│   └── UploadScreen.tsx    # Drag-drop upload screen
├── hooks/
│   └── usePdfEditor.ts      # Central state hook (all editor state + actions)
├── lib/
│   ├── pdfjs.ts             # pdf.js setup, page rendering, search
│   └── pdf-lib-utils.ts     # Export/merge/split/extract/rotate operations
└── types/
    └── index.ts             # Annotation/Tool/DisplayMode type definitions
```

## Feature Implementation Guide

### Annotations (overlay layer)
- Text boxes: `<div>` with `contentEditable` or `<textarea>` on double-click
- Sticky notes: icon + popup, double-click to edit
- Highlight: semi-transparent rectangles
- Shapes (rect/circle): `<div>` with border/borderRadius
- Line/arrow: rotated `<div>` with CSS transform, arrow head via border trick
- Freehand: `<svg><path>` with mouse capture
- Stamps: bordered box with rotated text
- Images: `<img>` with data URL
- Signature: `<img>` from canvas data URL
- Redaction: solid black `<div>`

### Drag/Move Annotations
Capture `mousedown` on annotation, track `mousemove` on `window`, update x/y in 0–1000 space using canvas bounding rect ratio.

### Page Operations
- Delete: remove annotations for page, shift indices, update thumbnails
- Add blank: increment numPages, insert rotation/thumbnail entry
- Reorder: splice arrays, remap annotation pageIndex
- Rotate: store per-page rotation array, apply during render

### Merge/Split
- Client-side: `pdf-lib` `copyPages` + `addPage` for merge; `copyPages` subset for split
- Server-side: API routes accept FormData (merge) or JSON with base64 (split)

### Search
Use `pdfDocument.getPage()` → `getTextContent()` → search through items. Store results as `{ pageIndex, match }[]`.

### Signatures
- HTML `<canvas>` with mouse/touch drawing
- `canvas.toDataURL("image/png")` → store as annotation `dataUrl`
- Save to `localStorage` for reuse

## Common Pitfalls

1. **Forgetting `"use client"` on pdf.js/pdf-lib utility files.** Both libraries use browser APIs (Worker, Canvas, atob/btoa). Any file importing them needs the directive.

2. **Using `--turbopack` when `canvas: false` webpack alias is needed.** Turbopack doesn't support `config.resolve.alias` the same way. Use plain `next build` / `next dev` without turbopack flag.

3. **Not copying `Uint8Array` to `ArrayBuffer` before `new Blob()`.** TS 5.7+ type error. Always use the copy pattern (see TypeScript Pitfalls #1).

4. **Using `StandardFonts.HelveticaItalic`.** It doesn't exist. Use `StandardFonts.HelveticaOblique`.

5. **Storing annotation coordinates in pixel space.** They break when zoom changes. Always use normalized 0–1000 space and convert at render time.

6. **Forgetting pdf.js uses 1-indexed pages.** `getPage(pageIndex + 1)` when your app uses 0-indexed pages.

7. **Not handling `ignoreEncryption: true` in `PDFDocument.load()`.** Password-protected PDFs will throw without this flag (you can't edit them, but you can at least load).

8. **Letting API route `NextResponse` return raw `Uint8Array`.** Type error in TS 5.7+. Copy to `ArrayBuffer` first.

## Verification Checklist

- [ ] `next.config.mjs` has `config.resolve.alias.canvas = false`
- [ ] `pdfjs.ts` has `"use client"` and worker setup via `import.meta.url`
- [ ] `package.json` dev script uses correct port, no turbopack flag
- [ ] All `new Blob([bytes])` calls copy to `ArrayBuffer` first
- [ ] `StandardFonts.HelveticaOblique` used (not `HelveticaItalic`)
- [ ] Annotation coordinates stored in 0–1000 space
- [ ] `pdfDocument.getPage(pageIndex + 1)` for 1-indexed pdf.js pages
- [ ] `npm run build` passes with zero type errors (warnings OK)
- [ ] `postcss.config.mjs` uses `@tailwindcss/postcss` (not `tailwindcss` plugin directly)