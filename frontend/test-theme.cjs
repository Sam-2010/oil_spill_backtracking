const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 }
  });

  console.log('[TEST] Loading login page...');
  await page.goto('http://localhost:8000', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3000);

  // Test 1: Check dark theme applied
  const bodyBg = await page.evaluate(() => {
    return getComputedStyle(document.body).backgroundColor;
  });
  console.log(`[TEST] Body background (dark): ${bodyBg}`);
  const isDark = bodyBg === 'rgb(5, 8, 10)' || bodyBg === '#05080a' || bodyBg === 'rgba(0,0,0,0)';
  console.log(`[PASS] Dark theme loaded: ${isDark ? 'YES' : 'NO'}`);

  // Test 2: Check CSS variables
  const vars = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    return {
      colorAmber: root.getPropertyValue('--color-amber').trim(),
      colorNominal: root.getPropertyValue('--color-nominal').trim(),
      colorError: root.getPropertyValue('--color-error').trim(),
      bgVoid: root.getPropertyValue('--bg-void').trim(),
    };
  });
  console.log('[TEST] CSS Variables:', vars);
  const hasNewColors = vars.colorAmber.toLowerCase() === '#e8a020';
  console.log(`[PASS] New color system applied: ${hasNewColors ? 'YES' : 'NO'}`);

  // Test 3: Login
  await page.fill('input[type="email"]', 'command@spill2source.io');
  await page.fill('input[type="password"]', 'maritime2026');
  await page.click('button.terminal-submit');
  await page.waitForTimeout(4000);

  // Test 4: Check header
  const header = await page.$('.hdr');
  console.log(`[PASS] Header rendered: ${header ? 'YES' : 'NO'}`);

  // Test 5: Check theme toggle
  const themeBtn = await page.$('.theme-toggle-btn');
  console.log(`[PASS] Theme toggle exists: ${themeBtn ? 'YES' : 'NO'}`);

  // Screenshot dark
  await page.screenshot({ path: 'test-results/theme-test-dark.png', fullPage: false });
  console.log('[TEST] Screenshot: test-results/theme-test-dark.png');

  // Test 6: Toggle theme and screenshot light
  if (themeBtn) {
    console.log('[TEST] Toggling to light theme...');
    await themeBtn.click();
    await page.waitForTimeout(2000);
    const bodyBgLight = await page.evaluate(() => {
      return getComputedStyle(document.body).backgroundColor;
    });
    console.log(`[TEST] Body background (light): ${bodyBgLight}`);
    await page.screenshot({ path: 'test-results/theme-test-light.png', fullPage: false });
    console.log('[TEST] Screenshot: test-results/theme-test-light.png');
  }

  console.log('\n[Test Complete]');
  await browser.close();
})();
