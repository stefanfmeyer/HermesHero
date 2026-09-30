---
name: obscura-browser
description: Headless browser for AI agents and web scraping — lightweight Rust-based alternative to headless Chrome, with built-in anti-detection
trigger: web scraping, headless browser, AI agent browsing, anti-detect browser, puppeteer替代, playwright替代, 网页爬取
---

# Obscura — Headless Browser for AI Agents

## What is it?
**Obscura** is an open-source headless browser built in Rust, designed for web scraping and AI agent automation. It's a drop-in replacement for headless Chrome with Puppeteer/Playwright.

**Repo**: https://github.com/h4ckf0r0day/obscura  
**Stars**: ~9.1k | **Forks**: ~572

## Key Advantages over Headless Chrome

| Metric | Obscura | Headless Chrome |
|--------|---------|-----------------|
| Memory | **30 MB** | 200+ MB |
| Binary size | **70 MB** | 300+ MB |
| Anti-detect | **Built-in** | None |
| Page load | **85 ms** | ~500 ms |
| Startup | **Instant** | ~2s |
| Puppeteer | ✅ Yes | ✅ Yes |
| Playwright | ✅ Yes | ✅ Yes |

## Installation

### Pre-built binaries (recommended)
```bash
# Linux
curl -L https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-linux-x86_64.tar.gz | tar -xz

# macOS (Intel)
curl -L https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-macos-x86_64.tar.gz | tar -xz

# macOS (Apple Silicon)
curl -L https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-macos-arm64.tar.gz | tar -xz

# Windows
curl -L https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-windows-x86_64.zip -o obscura.zip && unzip obscura.zip
```

### From source (requires Rust)
```bash
cargo install obscura
```

## Usage with Puppeteer
```javascript
import puppeteer from 'puppeteer';

const browser = await puppeteer.launch({
  executablePath: './obscura',
  headless: true,
  args: ['--no-sandbox']
});

const page = await browser.newPage();
await page.goto('https://example.com');
const content = await page.content();
await browser.close();
```

## Usage with Playwright
```javascript
import { chromium } from 'playwright';

const browser = await chromium.launch({
  executablePath: './obscura',
  headless: true,
  args: ['--no-sandbox']
});

const page = await browser.newPage();
await page.goto('https://example.com');
const content = await page.content();
await browser.close();
```

## CLI Mode
```bash
./obscura --remote-debugging-port=9222
./obscura --window-size=1920,1080
```

## When to Use
- **AI agent web browsing** — lightweight, anti-detect, fast
- **Web scraping at scale** — low memory, instant startup
- **Replacing Puppeteer/Playwright with Chrome** — drop-in replacement
- **Stealth scraping** — built-in anti-detection vs none in headless Chrome
