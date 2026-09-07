/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
  async rewrites() {
    const internalApi = process.env.INTERNAL_API_URL;
    if (!internalApi) return [];
    return [
      {
        source: '/api/:path*',
        destination: `${internalApi}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
