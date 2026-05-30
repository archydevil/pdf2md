import { PDFDocument, rgb, StandardFonts } from "pdf-lib";
import { writeFileSync } from "node:fs";

const doc = await PDFDocument.create();
const page = doc.addPage([400, 400]);
const font = await doc.embedFont(StandardFonts.Helvetica);

page.drawText("Test PDF for enrichment", { x: 40, y: 360, size: 18, font, color: rgb(0, 0, 0) });
page.drawText("This document has an image and a form field.", { x: 40, y: 330, size: 11, font });

// Build a valid 100x100 RGBA PNG (gradient) using zlib
import zlib from "node:zlib";
function crc32(buf) {
  let c = ~0;
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i];
    for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
  }
  return ~c >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const typeBuf = Buffer.from(type, "ascii");
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])), 0);
  return Buffer.concat([len, typeBuf, data, crc]);
}
function makePng(w, h) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // RGBA
  const raw = Buffer.alloc((w * 4 + 1) * h);
  let p = 0;
  for (let y = 0; y < h; y++) {
    raw[p++] = 0; // filter
    for (let x = 0; x < w; x++) {
      raw[p++] = Math.floor((x / w) * 255); // R
      raw[p++] = Math.floor((y / h) * 255); // G
      raw[p++] = 128; // B
      raw[p++] = 255; // A
    }
  }
  const idat = zlib.deflateSync(raw);
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", idat),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}
const pngBytes = makePng(100, 100);
const png = await doc.embedPng(pngBytes);
page.drawImage(png, { x: 40, y: 220, width: 100, height: 100 });

// Add a text form field with a value
const form = doc.getForm();
const tf = form.createTextField("fullName");
tf.setText("Mario Rossi");
tf.addToPage(page, { x: 40, y: 180, width: 200, height: 24 });

const bytes = await doc.save();
writeFileSync("tmp-test.pdf", bytes);
console.log("wrote tmp-test.pdf", bytes.length, "bytes");
