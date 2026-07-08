# Nitro Forge Website

`website/` is a fully static site (plain HTML/CSS/JS, zero dependencies, zero
build step) that mirrors the app's dark + baby-blue design system.

## Pages

| File | Purpose |
|---|---|
| `index.html` | Home: hero, animated app mockup, features grid, download section, footer |
| `support.html` | FAQ / how to get help / safety promise |
| `privacy.html` | Privacy policy (matches the app's actual behavior) |
| `terms.html` | Terms of use |

Shared assets: `css/style.css` (design tokens at the top match
`desktop/src/index.css`), `js/main.js` (scroll-reveal animations).

## Point the download button at your installer

`index.html` links to:

```
https://github.com/Trb-Studios/NitroForge/releases/latest
```

Update this href (2 places: hero + download card) if the repo name differs, or
link directly to a specific asset:
`.../releases/latest/download/Nitro.Forge_2.0.0_x64-setup.exe`

## Deploying

Any static host works - no server code required.

**GitHub Pages (free, easiest):**
1. Repo → Settings → Pages → Source: *Deploy from a branch*
2. Branch `main`, folder `/website` (or copy `website/` into a `gh-pages` branch root)
3. Site appears at `https://<user>.github.io/<repo>/`

**Cloudflare Pages / Netlify / Vercel:** create a project from the repo, set
the output directory to `website`, no build command.

## Editing tips

* Colors: change once in the `:root` block of `css/style.css`.
* Keep it dependency-free - the site loads in one round trip and can't break.
* Crash-report ingestion endpoint (optional) is documented in
  [DISCORD_INTEGRATION.md](DISCORD_INTEGRATION.md) §4 - it is separate from
  this static site.
