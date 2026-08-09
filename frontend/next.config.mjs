const securityHeaders = [
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data:",
      "font-src 'self'",
      "connect-src 'self'",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ].join("; "),
  },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
];

const nextConfig = {
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },

  async rewrites() {
    const apiBaseUrl = (process.env.API_BASE_URL || "http://127.0.0.1:8017").replace(/\/$/, "");

    return {
      beforeFiles: [
        { source: "/api/:path*", destination: `${apiBaseUrl}/api/:path*` },
        { source: "/", destination: "/index.html" },
        { source: "/analysis", destination: "/analysis.html" },
        { source: "/strategy", destination: "/strategy.html" },
        { source: "/tools", destination: "/tools.html" },
        { source: "/admin", destination: "/admin.html" },
        { source: "/privacy", destination: "/privacy.html" },
      ],
    };
  },
};

export default nextConfig;
