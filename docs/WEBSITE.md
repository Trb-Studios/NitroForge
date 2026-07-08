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

## The download button

The installer is hosted **on the site itself** at
`website/downloads/NitroForgeSetup.exe`, so the button is a direct download -
one click, no GitHub page in between. After building a new installer
(`scripts\build.ps1`), refresh it with:

```powershell
Copy-Item "desktop\src-tauri\target\release\bundle\nsis\Nitro Forge_*_x64-setup.exe" `
          "website\downloads\NitroForgeSetup.exe" -Force
```

commit, and push - the Pages workflow redeploys automatically.

(Alternative: create a GitHub Release and point the button at
`.../releases/latest/download/<asset>.exe` if you'd rather not keep the
binary in the repo.)

## Deploying

Deployment is automated: `.github/workflows/pages.yml` publishes `website/`
to **GitHub Pages** on every push that touches it. First-time setup, if the
workflow can't self-enable Pages: repo → Settings → Pages → Source:
*GitHub Actions*, then re-run the workflow.

Site URL: `https://<user>.github.io/<repo>/`

**Cloudflare Pages / Netlify / Vercel:** create a project from the repo, set
the output directory to `website`, no build command.

## Editing tips

* Colors: change once in the `:root` block of `css/style.css`.
* Keep it dependency-free - the site loads in one round trip and can't break.
* Crash-report ingestion endpoint (optional) is documented in
  [DISCORD_INTEGRATION.md](DISCORD_INTEGRATION.md) §4 - it is separate from
  this static site.
