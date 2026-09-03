// Rendert die drei Vorschau-Layouts als Full-Page-PNG nach screenshots/.
//
//   node shoot_previews.mjs
//
// Voraussetzung: Playwright + ein Chromium. Beides ist in der Remote-Umgebung
// global installiert, deshalb der absolute Import statt eines lokalen
// node_modules-Verzeichnisses - das Repo soll dependency-frei bleiben.
// PW / CHROME lassen sich per Umgebungsvariable ueberschreiben.
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW ?? '/opt/node22/lib/node_modules/playwright');

const dir = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(dir, 'screenshots');

const VARIANTS = [
  ['a.html', 'variante-a-timeline'],
  ['b.html', 'variante-b-master-detail'],
  ['c.html', 'variante-c-matrix'],
];

const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
});

for (const [file, name] of VARIANTS) {
  const ctx = await browser.newContext({
    viewport: { width: 1680, height: 1050 },
    deviceScaleFactor: 2,          // 2x, sonst franst die 1px-Matrix aus
  });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e)));

  await page.goto('file://' + path.join(dir, file), { waitUntil: 'load', timeout: 30_000 });
  // Die Layouts zeichnen ihre SVGs erst nach dem Font-Load neu (Textbreiten),
  // deshalb erst fonts.ready abwarten, dann kurz nachlaufen lassen.
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1200);

  await page.screenshot({ path: path.join(out, name + '.png'), fullPage: true });
  console.log(name, errs.length ? 'FEHLER: ' + errs.join(' | ') : 'ok');
  await ctx.close();
}

await browser.close();
