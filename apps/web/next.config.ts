import type { NextConfig } from "next";

const configuredApiUrl = (
    process.env.RENDER_API_URL ??
    process.env.INTERNAL_API_URL ??
    (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined)
)?.replace(/\/$/, "");

const nextConfig: NextConfig = {
    output: "standalone",
    experimental: {
        proxyTimeout: 120_000,
    },
    async rewrites() {
        if (!configuredApiUrl) {
            return [];
        }

        return [
            {
                source: "/api/:path*",
                destination: `${configuredApiUrl}/api/:path*`,
            },
        ];
    },
};

export default nextConfig;
