// Render the One Touch Resolve HTML slides to PNG.
//
//   node render.js <input.html> <output.png>
//
// Screenshots the .slide element at 2x (1280x720 -> 2560x1440). Reuses the
// puppeteer install from ../../agentic-studio-arch if this folder has none.
const path = require("path");

async function main() {
  let puppeteer;
  try {
    puppeteer = require("puppeteer");
  } catch {
    // Fall back to the shared install elsewhere in the environment.
    puppeteer = require(path.resolve(
      __dirname,
      "../../agentic-studio-arch/node_modules/puppeteer"
    ));
  }

  const file = process.argv[2];
  const out = process.argv[3];
  if (!file || !out) {
    console.error("usage: node render.js <input.html> <output.png>");
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1000, deviceScaleFactor: 2 });
  await page.goto("file://" + path.resolve(file), { waitUntil: "networkidle0" });
  await page.evaluateHandle("document.fonts.ready");
  await new Promise((r) => setTimeout(r, 400));
  const el = await page.$(".slide");
  await el.screenshot({ path: out });
  await browser.close();
  console.log("rendered", out);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
