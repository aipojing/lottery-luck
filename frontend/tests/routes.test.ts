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
});
