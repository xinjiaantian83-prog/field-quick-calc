import { cp, mkdir, rm } from "node:fs/promises";
import { existsSync } from "node:fs";

const root = new URL("../", import.meta.url);
const dist = new URL("dist/", root);
const copyItems = ["index.html", "css", "js", "icons"];

await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });

for (const item of copyItems) {
  const src = new URL(item, root);
  if (!existsSync(src)) continue;
  await cp(src, new URL(item, dist), { recursive: true });
}

console.log("Built Field Quick Calc in dist");
