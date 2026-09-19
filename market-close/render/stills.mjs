// 한 번 묶고 여러 장 — node stills.mjs <props.json> <outdir> <comp> <frame:name,...>  (음성 전 화면 미리 보기·썸네일용)
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
const [propsPath, outDir, compId, list] = process.argv.slice(2);
const inputProps = JSON.parse(fs.readFileSync(propsPath, "utf-8"));
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts") });
const composition = await selectComposition({ serveUrl, id: compId, inputProps });
fs.mkdirSync(outDir, { recursive: true });
for (const item of list.split(",")) {
  const [fr, name] = item.split(":");
  const output = path.join(outDir, `${name}.png`);
  await renderStill({ composition, serveUrl, output, inputProps, frame: Number(fr), scale: 0.5 });
  console.log("ok", name);
}
