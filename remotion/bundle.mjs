import { bundle } from "@remotion/bundler";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const main = async () => {
  const entryPoint = path.join(__dirname, "src/index.tsx");
  console.log(`Bundling entry point: ${entryPoint}`);
  
  const bundleLocation = await bundle({
    entryPoint: entryPoint,
    onProgress: (p) => {
      process.stdout.write(`\rBundling: ${Math.round(p * 100)}%`);
    },
  });
  
  console.log("\nBUNDLE_PATH:" + bundleLocation);
};

main().catch(console.error);
