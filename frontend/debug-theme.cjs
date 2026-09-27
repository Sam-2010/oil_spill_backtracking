const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 }
  });

  console.log('[DEBUG] Loading page...');
  await page.goto('http://localhost:8000', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);

  // Check actual computed styles
  const styles = await page.evaluate(() => {
    const body = document.body;
    const html = document.documentElement;
    const appHud = document.querySelector('.app-hud');
    const root = getComputedStyle(html);

    return {
      // HTML root
      htmlBg: getComputedStyle(html).backgroundColor,
      htmlDataTheme: html.getAttribute('data-theme'),

      // Body
      bodyBg: getComputedStyle(body).backgroundColor,
      bodyOverflow: getComputedStyle(body).overflow,

      // App HUD
      appHudExists: !!appHud,
      appHudDataTheme: appHud?.getAttribute('data-theme'),
      appHudBg: appHud ? getComputedStyle(appHud).backgroundColor : 'N/A',

      // CSS Variables from :root
      bgVoid: root.getPropertyValue('--bg-void').trim(),
      textPrimary: root.getComputedStyle(document.body).color,
    };
  });

  console.log('[DEBUG] Computed Styles:', JSON.stringify(styles, null, 2));

  // Take screenshot
  await page.screenshot({ path: 'test-results/debug-theme.png', fullPage: true });
  console.log('[DEBUG] Screenshot saved');

  await browser.close();
})();
