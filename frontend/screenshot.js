const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'auth-panel-screenshot.png', fullPage: false });
  console.log('Screenshot saved to auth-panel-screenshot.png');
  await browser.close();
})();
