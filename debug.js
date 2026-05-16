import puppeteer from 'puppeteer';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', err => errors.push('PAGEERROR: ' + err.message));

  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle0', timeout: 15000 }).catch(e => {
    console.log('GOTO ERROR:', e.message);
  });

  await new Promise(r => setTimeout(r, 2000));

  const screenshotPath = path.join(__dirname, 'debug_screenshot.png');
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log('Screenshot saved:', screenshotPath);

  const bodyText = await page.evaluate(() => document.body?.innerText?.substring(0, 500) || '(empty)');
  console.log('BODY TEXT:', bodyText);
  console.log('URL:', page.url());
  console.log('ERRORS:', errors.length === 0 ? 'NONE' : errors.join('\n'));

  await browser.close();
})();
