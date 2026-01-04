/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  webpack: (config) => {
    // Fix for canvas dependency in react-pdf
    config.resolve.alias.canvas = false;
    return config;
  },
}

module.exports = nextConfig
