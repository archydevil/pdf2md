/** @type {import('next').NextConfig} */
const isDesktop = process.env.BUILD_TARGET === 'desktop'

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
}

export default nextConfig
