import { withPostHogConfig } from '@posthog/nextjs-config';

/** @type {import('next').NextConfig} */
const nextConfig = {
  // PostHog reverse proxy: the browser sends events to /ingest on our own domain.
  async rewrites() {
    return [
      { source: '/ingest/static/:path*', destination: 'https://eu-assets.i.posthog.com/static/:path*' },
      { source: '/ingest/array/:path*', destination: 'https://eu-assets.i.posthog.com/array/:path*' },
      { source: '/ingest/:path*', destination: 'https://eu.i.posthog.com/:path*' },
    ];
  },
  // PostHog API paths end in a slash; Next would otherwise redirect them.
  skipTrailingSlashRedirect: true,
};

// Upload source maps to PostHog Error tracking on builds that have the credentials (Vercel).
const uploadSourceMaps = Boolean(process.env.POSTHOG_PERSONAL_API_KEY && process.env.POSTHOG_PROJECT_ID);

export default uploadSourceMaps
  ? withPostHogConfig(nextConfig, {
    personalApiKey: process.env.POSTHOG_PERSONAL_API_KEY,
    projectId: process.env.POSTHOG_PROJECT_ID,
    host: 'https://eu.posthog.com',
    sourcemaps: { enabled: true, deleteAfterUpload: true },
  })
  : nextConfig;
