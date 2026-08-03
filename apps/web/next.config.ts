import type { NextConfig } from "next";

const renderApiUrl = process.env.RENDER_API_URL?.replace(/\/$/, "");

const nextConfig: NextConfig = {
    output: "standalone",
    async rewrites() {
        if (!renderApiUrl) {
            return [];
        }

        return [
            {
                source: "/api/:path*",
                destination: `${renderApiUrl}/api/:path*`,
            },
        ];
    },
};

export default nextConfig;
