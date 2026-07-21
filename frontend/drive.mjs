import { chromium } from "playwright";

const shots = "/private/tmp/claude-501/-Users-sameer-ET/71d8bdcf-e53c-42ce-94e0-3740e35ac165/scratchpad";
const errors = [];

const browser = await chromium.launch({ args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
page.on("console", (msg) => {
  if (msg.type() === "error") errors.push(msg.text());
});
page.on("pageerror", (err) => errors.push("pageerror: " + err.message));

await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForSelector("text=PlantMind");
await page.waitForTimeout(500);
await page.screenshot({ path: `${shots}/1-briefings.png`, fullPage: true });

const btn = page.getByRole("button", { name: /Open WO-2026-4471/i });
await btn.click();
await page.waitForTimeout(1500);
await page.screenshot({ path: `${shots}/2-briefing-fired.png`, fullPage: true });

await page.getByRole("button", { name: /Explorer/ }).first().click();
await page.waitForTimeout(2000);
await page.screenshot({ path: `${shots}/3-explorer.png`, fullPage: true });

const canvas = page.locator("canvas").first();
const box = await canvas.boundingBox();
if (box) {
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${shots}/4-explorer-click.png`, fullPage: true });
}

await page.getByRole("button", { name: /^.{0,3}Ask$/ }).first().click();
await page.waitForTimeout(300);
await page.getByPlaceholder(/Ask about any equipment/i).fill("What incidents has P-101A had?");
await page.getByRole("button", { name: "Ask", exact: true }).click();
await page.waitForTimeout(1000);
await page.screenshot({ path: `${shots}/5-ask.png`, fullPage: true });

await page.getByRole("button", { name: /Retirement/ }).first().click();
await page.waitForTimeout(1000);
await page.screenshot({ path: `${shots}/6-retirement.png`, fullPage: true });

console.log("CONSOLE_ERRORS:", JSON.stringify(errors));
await browser.close();
