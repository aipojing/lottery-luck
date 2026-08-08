const nextConfig = {
  output: "standalone",
  async rewrites() {
    const apiBaseUrl = (process.env.API_BASE_URL || "http://127.0.0.1:8017").replace(/\/$/, "");

    return {
      beforeFiles: [
        { source: "/api/:path*", destination: `${apiBaseUrl}/api/:path*` },
        { source: "/", destination: "/index.html" },
        { source: "/analysis", destination: "/analysis.html" },
        { source: "/strategy", destination: "/strategy.html" },
        { source: "/admin", destination: "/admin.html" },
        { source: "/privacy", destination: "/privacy.html" },
      ],
    };
  },
};

export default nextConfig;
