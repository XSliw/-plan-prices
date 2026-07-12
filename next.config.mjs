/** @type {import('next').NextConfig} */
const isGitHubPages = process.env.GITHUB_ACTIONS === 'true'
const repository = process.env.GITHUB_REPOSITORY?.split('/')[1] ?? ''
const basePath = isGitHubPages && repository ? `/${repository}` : ''

const nextConfig = {
  output: isGitHubPages ? 'export' : undefined,
  basePath,
  trailingSlash: isGitHubPages,
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
