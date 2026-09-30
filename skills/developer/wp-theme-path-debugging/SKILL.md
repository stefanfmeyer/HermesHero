---
name: wp-theme-path-debugging
description: Debug and fix broken asset/theme paths on WordPress sites where /app/themes/ URLs 404 despite files existing on the filesystem. Covers DB, PHP, source JSX, compiled JS bundles, and .htaccess approaches.
---

# WordPress Theme Path Debugging — Image/Asset URL Issues

## Problem
WordPress site serves assets (images, CSS, JS) at `/app/themes/` but the web server/web root only exposes `/wp-content/themes/`. Assets 404 despite existing on the filesystem.

## Root Cause Anatomy
When debugging path issues on WordPress sites, trace ALL layers — the bug is often spread across multiple:

1. **Database** — `wp_posts.post_content`, `wp_postmeta.meta_value` store serialized block data with hardcoded URLs. Run: `SELECT * FROM wp_posts WHERE post_content LIKE '%/app/themes/%';`
2. **PHP functions** — `get_theme_path_url()` or similar helpers returning wrong base path
3. **Source JSX/JS** — `parseMedia()` or similar functions checking for wrong path string
4. **Compiled JS bundle** — Webpack-compiled `.js` files in `build/` are what the browser actually loads. **Editing source `.jsx` files has ZERO effect until rebuilt**
5. **CSS defaults** — hardcoded URL defaults in `block.json`, `edit.js`
6. **PHP template files** — inline styles or JS with wrong paths

## Debugging Steps

### Step 1: Find ALL occurrences of the wrong path
```bash
grep -rn "/app/themes/" theme-directory/
```

### Step 2: Identify which layer is the actual browser culprit
- Check Network tab in browser DevTools for 404 URLs
- Check `curl -I https://domain.com/correct/path/to/asset.png` — if this 200s, the path itself works
- If source JSX has fix but site still broken → compiled bundle not updated

### Step 3: Fix compiled JS directly on server (fastest, no rebuild needed)
Find the compiled bundle:
```bash
grep -rln "parseMedia\|/app/themes/" build-directory/
```
Edit the `.js` file directly on server — change the string check from `/app/themes/` to `/wp-content/themes/`.

### Step 4: .htaccess redirect (alternative quick fix)
```apache
RewriteEngine On
RewriteRule ^app/themes/(.*)$ /wp-content/themes/$1 [R=301,L]
```

### Step 5: Fix DB
```sql
UPDATE wp_posts
SET post_content = REPLACE(post_content, '/app/themes/', '/wp-content/themes/')
WHERE post_content LIKE '%/app/themes/%';
```

### Step 6: Fix source + rebuild for long-term
- Fix source files (.jsx, .js, PHP)
- Run `npm run build` or `npm run build-blocks`
- Deploy compiled output

## Key Insight
On WordPress sites using webpack-compiled blocks (wp-scripts), the **browser loads compiled `.js` bundles from `build/`**, NOT the source `.jsx` files. A fix to source JSX does nothing until the webpack build re-runs and deploys.

### When fixing compiled bundles — go broad, not narrow
The broken path (`/app/themes/`) is often scattered across **every block's compiled output** — 26+ JS files, block.json metadata, and CSS files. A targeted fix on one block won't work:
```bash
# Fix ALL compiled files in one go
find build/ -name "*.js" -exec sed -i 's|/app/themes/|/wp-content/themes/|g' {} \;
find build/ \( -name "*.json" -o -name "*.css" \) -exec sed -i 's|/app/themes/|/wp-content/themes/|g' {} \;
```
The `parseMedia()` function is inlined per-block by webpack — it lives in multiple files, not a shared utility.

### NEVER change Tailwind's `lg` (or `md`/`sm`/`xl`) breakpoint for a menu tweak
Tailwind's default breakpoints (`sm`, `md`, `lg`, `xl`, `2xl`) are used site-wide by every block and component. Changing one for the menu will cascade and break:
- Container margins (`lg:mx-16`, `lg:px-12`)
- Layout switching (`lg:flex-row`, `lg:w-1/2`)
- Visibility classes (`lg:hidden`, `lg:block`)
- Column layouts in every block

**Instead**, create a custom named breakpoint just for the menu:
```js
// tailwind.config.js — screens section
screens: {
  'xs': '396px',
  'sm': '640px',
  'md': '768px',
  'lg': '1024px',     // ← KEEP at default!
  'menu-lg': '1466px', // ← Custom, only used in header
  'xl': '1280px',
  '2xl': '1536px',
  // ...
}
```
Then use `menu-lg:hidden` / `menu-lg:flex` / `menu-lg:block` in header.php — no cascading side effects.

## Tailwind arbitrary variants are dead strings in compiled bundles

Tailwind arbitrary variants like `[&_p]:m-0`, `[&_h2]:m-0` or `[&>*]:mx-0` **do not work** when added to compiled webpack bundles without a rebuild. These are Tailwind CSS classes that only generate real CSS during the build step — once the JSX is compiled into a minified `.js` bundle, they're just dead strings in className attributes.

**Instead, inject CSS directly into the DOM via JavaScript:**

```js
// For React/JSX bundles deployed via FTP without rebuild
var existing = document.querySelector("style#my-style-id");
if (!existing) {
  var style = document.createElement("style");
  style.id = "my-style-id";
  style.textContent = ".my-block-class h2,.my-block-class p{margin:0!important}";
  document.head.appendChild(style);
}
```

**Placement in compiled JSX bundles:**

Inject this code at the top of the component render function, right after the function signature opens. In a compiled webpack bundle (all one line), it looks like:

```js
function d({blockProps:t,mode:e,...}){
try{document.querySelector(\"style#lb-carousel-margins\")||(function(){var e=document.createElement(\"style\");e.id=\"lb-carousel-margins\";e.textContent=\".myproject-carousel-block h2,.myproject-carousel-block p{margin:0!important}\";document.head.appendChild(e)})()}catch(e){},
...
```

The try/catch is important — it prevents errors if `document` isn't available (SSR, headless contexts).

**Why this works:**
- Runs at component render time via live JavaScript executing in the browser
- Injects real CSS into `<head>` with higher specificity (`!important`)
- Only runs once due to the `querySelector` guard
- No build step, no Tailwind dependency, works immediately on FTP
- Survives WordPress content filters that might strip `<style>` tags from block output

## Source JSX changes require patching compiled bundles too

When editing a block's source `.jsx` file (in `application/blocks/`), the browser **never loads that file**. The browser loads webpack-compiled `.js` bundles from `build/blocks-application/`.

**Workflow for any source change:**

1. Edit the source `.jsx` file (for future rebuilds)
2. Find and patch the exact same string in the compiled `.js` bundle (for immediate effect)
3. FTP only the compiled bundle (not the source)

**How to find the right string in compiled output:**

Compiled bundles are minified but contain the same string literals. If you change:
```jsx
className="w-full mx-4 sm:mx-8 md:mx-12 lg:mx-16 xl:mx-32 2xl:mx-56"
```
to:
```jsx
className="w-auto mx-4 sm:mx-8 md:mx-12 lg:mx-16 xl:mx-32 2xl:mx-56"
```

Grep for the old string in the compiled bundle (it will be there verbatim, just in a long one-liner):
```bash
grep -rl 'w-full mx-4 sm:mx-8 md:mx-12 lg:mx-16 xl:mx-32 2xl:mx-56' build/ | sort
```

Then batch-patch all matching files:
```bash
grep -rl 'old-string' build/blocks-application/ | while read f; do
  sed -i '' 's|old-string|new-string|g' "$f"
done
```

**Class changes spread across many blocks:** A class like `w-full mx-4 sm:mx-8...` is used in 16+ block bundles. Don't fix just one — fix them all in one pass.

## Pitfall: single.php wrapping the_content() in margin containers

When a single blog post template wraps `the_content()` inside a container with margin classes:

```php
<!-- single.php -->
<div class="mx-4 sm:mx-8 md:mx-12 lg:mx-16 xl:mx-32 2xl:mx-56">
    <div class="post-content">
        <?php the_content(); ?>
    </div>
</div>
```

And the Gutenberg blocks inside `the_content()` (like `myproject-paragraph`) also render their own margin containers:

```jsx
<div className="mx-4 sm:mx-8 md:mx-12 lg:mx-16 xl:mx-32 2xl:mx-56 py-16">
    {paragraphContent}
</div>
```

You get **doubled margins** — content looks narrower and has excess padding on blog posts vs normal pages.

**Fix:** Don't wrap `the_content()` in a margin container — let the blocks handle their own spacing. Give the template's title/header section its own lightweight container with just padding:

```php
<!-- single.php -- fixed -->
<article>
    <div class="mb-12 py-16">   <!-- no mx-* classes, just spacing -->
        <h1><?= $postTitle ?></h1>
        <!-- meta -->
    </div>
    <div class="post-content">
        <?php the_content(); ?>  <!-- blocks handle their own margins -->
    </div>
</article>
```

## Prevention
- Use `get_template_directory_uri()` and `content_url()` in PHP — never hardcode paths
- Store only filenames in block attributes, not full URLs — construct URLs at render time
- Always rebuild + deploy after editing source block files
- Never change default Tailwind breakpoints for one-off menu changes; use custom named breakpoints
