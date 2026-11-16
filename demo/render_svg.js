// Rasterizza gli SVG dei livelli in PNG trasparenti con Chromium.
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch();
  const pg = await b.newPage();
  for (const j of jobs) {
    await pg.setViewportSize({ width: j.w, height: j.h });
    await pg.setContent(`<html><body style="margin:0;background:transparent">${fs.readFileSync(j.svg, 'utf8')}</body></html>`);
    await pg.screenshot({ path: j.png, omitBackground: true, clip: { x: 0, y: 0, width: j.w, height: j.h } });
    console.log('ok', j.png.split('/').pop());
  }
  await b.close();
})();
