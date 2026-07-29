/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    // Disables the client-side Router Cache for dynamic routes (default: 30s).
    // RCC's sync status must never be served from a stale client-side cache
    // after a real-time mutation (POST /sync) — every navigation between
    // Home/Dashboard/Creator Intelligence/Video Detail must hit the server for
    // fresh data. See docs/DECISIONS.md ADR-016 (sync consistency bugfix).
    staleTimes: {
      dynamic: 0,
    },
  },
};

module.exports = nextConfig;
