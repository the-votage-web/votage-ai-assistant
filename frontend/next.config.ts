import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/events',
        destination: '/api/events',
      },
      {
        source: '/event/register/:eventName',
        destination: '/api/events/:eventName/register',
      },
      {
        source: '/apis/checkin',
        destination: '/api/events/checkin',
      },
    ];
  },
};

export default nextConfig;
