import { renderMedia, selectComposition } from "@remotion/renderer";
import { readFileSync } from "fs";
import { parseArgs } from "util";

const { values } = parseArgs({
  args: process.argv.slice(2),
  options: {
    composition: { type: "string" },
    data:        { type: "string" },
    output:      { type: "string" },
    bundle:      { type: "string" },
  },
});

if (!values.composition || !values.data || !values.output || !values.bundle) {
  console.error("Usage: node render.mjs --composition <id> --data <path> --output <path> --bundle <path>");
  process.exit(1);
}

const main = async () => {
  const rawData = JSON.parse(readFileSync(values.data, "utf-8"));
  const inputProps = { data: rawData };
  const bundleLocation = values.bundle;

  console.log(`Selecting composition ${values.composition}...`);
  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: values.composition,
    inputProps,
  });

  console.log(`Rendering to ${values.output}...`);
  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: values.output,
    inputProps,
    chromiumOptions: {
      disableWebSecurity: true
    },
    onProgress: ({ progress }) => {
      process.stdout.write(`\rRendering: ${Math.round(progress * 100)}%`);
    },
  });

  console.log(`\nRender complete: ${values.output}`);
};

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
