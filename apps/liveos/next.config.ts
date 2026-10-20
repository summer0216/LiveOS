import type { NextConfig } from 'next';

const apiOrigin = (
  process.env.RENDER_API_URL
  ?? process.env.INTERNAL_API_URL
  ?? (process.env.NODE_ENV === 'development' ? 'http://127.0.0.1:8000' : undefined)
)?.replace(/\/$/, '');

const nextConfig: NextConfig = {
  allowedDevOrigins: process.env.NODE_ENV === 'development'
    ? process.env.LIVEOS_DEV_ORIGINS?.split(',').map((host) => host.trim()).filter(Boolean)
    : undefined,
  async rewrites() {
    return apiOrigin ? [{ source: '/api/:path*', destination: `${apiOrigin}/api/:path*` }] : [];
  },
};

export default nextConfig;
