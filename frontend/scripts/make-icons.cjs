const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

const appDir = path.join(process.cwd(), "app");

const flame = "M39 4.5C41 13.5 46 21 46 31.5C46 43.4 39.2 52.5 30.4 52.5C21.6 52.5 15 44.4 15 34.6C15 26 22 20.6 27 14.6C30.4 10.4 33.4 7.6 39 4.5ZM29.5 29C33 34 34.8 37.6 34.8 41.4C34.8 45 32.4 47.6 29.2 47.6C26 47.6 23.8 45 23.8 41.4C23.8 37.4 26.4 33.6 29.5 29Z";

function svg(size) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="${size}" height="${size}">` +
    `<defs><linearGradient id="g" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">` +
    `<stop offset="0" stop-color="#8b7aff"/><stop offset="1" stop-color="#5540ea"/></linearGradient></defs>` +
    `<rect width="64" height="64" rx="15" fill="url(#g)"/>` +
    `<path d="${flame}" fill="#ffffff" fill-rule="evenodd" transform="translate(32 32) scale(0.66) translate(-32 -32)"/>` +
    `</svg>`;
}

const iconSvg = svg(64);
fs.writeFileSync(path.join(appDir, "icon.svg"), iconSvg + "\n");

async function png(size, out) {
  const buf = await sharp(Buffer.from(svg(size))).resize(size, size).png({ compressionLevel: 9 }).toBuffer();
  fs.writeFileSync(out, buf);
  return buf;
}

(async () => {
  const sizes = [16, 32, 48];
  const images = [];
  for (const size of sizes) images.push(await png(size, path.join(appDir, "tmp-" + size + ".png")));

  const count = sizes.length;
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(count, 4);
  const entries = Buffer.alloc(16 * count);
  let offset = 6 + 16 * count;
  images.forEach((buf, i) => {
    const base = i * 16;
    entries.writeUInt8(sizes[i] >= 256 ? 0 : sizes[i], base);
    entries.writeUInt8(sizes[i] >= 256 ? 0 : sizes[i], base + 1);
    entries.writeUInt8(0, base + 2);
    entries.writeUInt8(0, base + 3);
    entries.writeUInt16LE(1, base + 4);
    entries.writeUInt16LE(32, base + 6);
    entries.writeUInt32LE(buf.length, base + 8);
    entries.writeUInt32LE(offset, base + 12);
    offset += buf.length;
  });
  fs.writeFileSync(path.join(appDir, "favicon.ico"), Buffer.concat([header, entries, ...images]));

  await png(180, path.join(appDir, "apple-icon.png"));
  await sharp(Buffer.from(svg(512))).resize(512, 512).png().toFile(path.join(appDir, "..", "public", "icon-512.png"));

  for (const size of sizes) fs.unlinkSync(path.join(appDir, "tmp-" + size + ".png"));
  console.log("icons written: " + fs.statSync(path.join(appDir, "favicon.ico")).size + " bytes ico, " + fs.statSync(path.join(appDir, "apple-icon.png")).size + " bytes apple");
})();