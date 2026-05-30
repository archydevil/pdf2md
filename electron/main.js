const { app, BrowserWindow, shell, protocol, net } = require("electron")
const path = require("node:path")
const { pathToFileURL } = require("node:url")

const isDev = !app.isPackaged && !!process.env.ELECTRON_START_URL

// Directory holding the static Next.js export (`next build` with output: 'export').
const OUT_DIR = path.join(__dirname, "..", "out")

// Register a privileged custom scheme so the static export behaves like a real
// origin (fetch, secure context, standard URL resolution for absolute paths).
protocol.registerSchemesAsPrivileged([
  {
    scheme: "app",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
    },
  },
])

function resolveFilePath(requestUrl) {
  const { pathname } = new URL(requestUrl)
  let relativePath = decodeURIComponent(pathname)

  // Root or directory requests map to index.html
  if (relativePath === "/" || relativePath === "") {
    relativePath = "/index.html"
  }

  let filePath = path.join(OUT_DIR, relativePath)

  // If the path has no extension, try the matching .html file (Next routes).
  if (!path.extname(filePath)) {
    filePath = `${filePath}.html`
  }

  // Prevent path traversal outside the export directory.
  const normalized = path.normalize(filePath)
  if (!normalized.startsWith(OUT_DIR)) {
    return path.join(OUT_DIR, "index.html")
  }
  return normalized
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 820,
    minWidth: 720,
    minHeight: 600,
    backgroundColor: "#0a0a0a",
    title: "PDF to Markdown",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  // Open external links (e.g. GitHub, Twitter) in the user's default browser.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      shell.openExternal(url)
      return { action: "deny" }
    }
    return { action: "allow" }
  })

  if (isDev) {
    win.loadURL(process.env.ELECTRON_START_URL)
    win.webContents.openDevTools({ mode: "detach" })
  } else {
    win.loadURL("app://bundle/index.html")
  }
}

app.whenReady().then(() => {
  protocol.handle("app", (request) => {
    const filePath = resolveFilePath(request.url)
    return net.fetch(pathToFileURL(filePath).toString())
  })

  createWindow()

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit()
  }
})
