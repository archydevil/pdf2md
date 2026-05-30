/** @type {import('next').NextConfig} */
const isDesktop = process.env.BUILD_TARGET === 'desktop'
const isDocker = process.env.BUILD_TARGET === 'docker'

const nextConfig = {
  images: {
    unoptimized: true,
  },
  // For the standalone desktop (Electron) build we produce a fully static
  // export that is loaded from the local filesystem.
  ...(isDesktop
    ? {
        output: 'export',
        assetPrefix: './',
      }
    : {}),
  // For the Docker image we emit a self-contained Node server bundle.
  ...(isDocker
    ? {
        output: 'standalone',
      }
    : {}),
}

export default nextConfig
