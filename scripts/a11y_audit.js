/* Accessibility and layout audit of the page as drawn. Paste into the browser console (or run it with a
   browser tool) on any page of the app; it reads the page and changes nothing.

   It returns, for the page as it is drawn now:
     contrast    text whose colour against its background is below WCAG AA (4.5:1, or 3:1 for large text:
                 24px, or 18.66px bold). The background is the first solid one found going up the page;
                 text on an image or a gradient is not measured.
     unlabelled  inputs, selects and textareas with no accessible name (label, aria-label, aria-labelledby, title)
     overflow    elements wider than the window, which make the page scroll sideways
     lang        the <html lang> value
   The thresholds are WCAG 2.1 SC 1.4.3; the rest is our own rule. */
(() => {
  /* "rgb(r, g, b[, a])", or "color(srgb r g b[ / a])" with channels 0-1, which color-mix() gives */
  const rgb = (s) => { const v = (s.match(/[\d.]+/g) || []).map(Number);
    return /^color\(srgb/.test(s) ? v.map((x, i) => (i < 3 ? x * 255 : x)) : v; };
  const lum = ([r, g, b]) => [r, g, b].map((v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; })
    .reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const blend = (fg, bg) => { const a = fg[3] === undefined ? 1 : fg[3]; return [0, 1, 2].map((i) => fg[i] * a + bg[i] * (1 - a)); };
  function background(el) {
    const layers = [];
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== "none" && !/gradient/.test(cs.backgroundImage)) return null;
      const c = rgb(cs.backgroundColor);
      if (c.length >= 3 && (c[3] === undefined || c[3] > 0)) { layers.push(c); if (c[3] === undefined || c[3] >= 1) break; }
    }
    let base = [255, 255, 255];
    for (const c of layers.reverse()) base = blend(c, base);
    return base;
  }
  const visible = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && Number(cs.opacity) > 0.1; };
  const contrast = [], seen = new Set();
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = walk.nextNode());) {
    const text = n.textContent.trim();
    const el = n.parentElement;
    if (!text || !el || seen.has(el) || !visible(el) || el.closest(".visually-hidden,svg,script,style")) continue;
    seen.add(el);
    const cs = getComputedStyle(el);
    const bg = background(el);
    if (!bg) continue;
    const fg = blend(rgb(cs.color), bg);
    const size = parseFloat(cs.fontSize), bold = Number(cs.fontWeight) >= 700;
    const need = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
    const r = ratio(fg, bg);
    if (r < need) contrast.push({ text: text.slice(0, 60), ratio: Math.round(r * 100) / 100, need, cls: el.className || el.tagName });
  }
  const name = (el) => el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || el.title
    || (el.labels && el.labels.length && el.labels[0].textContent.trim());
  const unlabelled = [...document.querySelectorAll("input:not([type=hidden]),select,textarea")].filter((el) => visible(el) && !name(el))
    .map((el) => el.outerHTML.slice(0, 100));
  const w = document.documentElement.clientWidth;
  const overflow = [...document.querySelectorAll("body *")].filter((el) => { const r = el.getBoundingClientRect();
    return visible(el) && r.right > w + 1 && !el.closest(".table-wrap,.steps,[style*=overflow]"); })
    .filter((el, _, all) => !all.some((p) => p !== el && p.contains(el))).map((el) => `${el.tagName}.${el.className}`.slice(0, 80));
  return { contrast, unlabelled, overflow, pageScrollsSideways: document.documentElement.scrollWidth > w + 1,
    lang: document.documentElement.lang, width: w };
})();
