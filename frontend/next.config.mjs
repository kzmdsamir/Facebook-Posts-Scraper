/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Standalone output keeps the server self-contained for the Docker image.
  output: "standalone",
};

export default nextConfig;