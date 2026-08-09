import { describe, expect, it } from "vitest";
import nextConfig from "../next.config.mjs";

describe("legacy compatibility routes", () => {
  it("leaves deployment output to Vercel's Next.js builder", () => {
    expect(nextConfig).not.toHaveProperty("output");
  });

  it("keeps product URLs stable", async () => {
    const rewrites = await nextConfig.rewrites();
    expect(rewrites.beforeFiles).toEqual(
      expect.arrayContaining([
        { source: "/", destination: "/index.html" },
        { source: "/analysis", destination: "/analysis.html" },
        { source: "/strategy", destination: "/strategy.html" },
        { source: "/tools", destination: "/tools.html" },
        { source: "/admin", destination: "/admin.html" },
      ]),
    );
  });

  it("proxies API calls to the configured FastAPI origin", async () => {
    process.env.API_BASE_URL = "https://api.example.test";
    const rewrites = await nextConfig.rewrites();
    expect(rewrites.beforeFiles).toContainEqual({
      source: "/api/:path*",
      destination: "https://api.example.test/api/:path*",
    });
  });

  it("sets browser security headers on every public route", async () => {
    const rules = await nextConfig.headers();
    const allRoutes = rules.find((rule) => rule.source === "/:path*");
    const headers = Object.fromEntries(
      (allRoutes?.headers || []).map((header) => [header.key, header.value]),
    );

    expect(headers["Content-Security-Policy"]).toContain("default-src 'self'");
    expect(headers["Content-Security-Policy"]).toContain("frame-ancestors 'none'");
    expect(headers["Content-Security-Policy"]).toContain("object-src 'none'");
    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
    expect(headers["X-Frame-Options"]).toBe("DENY");
    expect(headers["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["Permissions-Policy"]).toContain("camera=()");
  });
});
