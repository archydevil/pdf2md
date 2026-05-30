# PDF to Markdown — Desktop app

A standalone, offline desktop version of the app for **macOS**, **Windows** and **Linux**,
built with [Electron](https://www.electronjs.org/) wrapping the static Next.js export.
Everything (PDF → Markdown/TXT/DOCX) runs locally — no network required.

## Prerequisites

- Node.js 20+
- Run `npm install` once

## Run the desktop app (development)

Build the static export and open the Electron window:

```bash
npm run desktop
```

To develop against the live Next.js dev server with hot reload:

```bash
# terminal 1
npm run dev
# terminal 2
npm run desktop:dev
```

## Build installers

Installers are written to the `release/` folder.

```bash
npm run dist:mac    # macOS  -> release/*.dmg  (arm64 + x64)
npm run dist:win    # Windows -> release/*.exe (NSIS installer)
npm run dist        # current OS default targets
```

Notes:

- **Windows builds from macOS/Linux** require `wine` to be installed
  (`brew install --cask wine-stable`). Building each OS on its own platform
  (or in CI) is the most reliable option.
- The macOS `.dmg` is **unsigned**. On first launch Gatekeeper may block it;
  right‑click the app → **Open**, or run
  `xattr -dr com.apple.quarantine "/Applications/PDF to Markdown.app"`.
  For distribution, configure Apple code signing / notarization.

## How it works

- `npm run desktop:export` runs `next build` with `BUILD_TARGET=desktop`, which
  enables `output: 'export'` in [next.config.mjs](../next.config.mjs) and emits a
  fully static site into `out/`.
- [electron/main.js](main.js) registers a custom, secure `app://` protocol that
  serves the files in `out/`, so absolute asset paths resolve correctly without a
  local web server. External links open in the system browser.
- Web-only Vercel Analytics is disabled in the desktop build.
- Packaging is configured under the `build` key in [package.json](../package.json).
</content>
