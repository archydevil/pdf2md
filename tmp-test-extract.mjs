import { readFileSync } from "node:fs";
import { extractImages, getDocumentProxy, getResolvedPDFJS } from "unpdf";

const buf = new Uint8Array(readFileSync("tmp-test.pdf"));
const { OPS } = await getResolvedPDFJS();
const pdf = await getDocumentProxy(buf);
const page = await pdf.getPage(1);
const ops = await page.getOperatorList();
const names = Object.fromEntries(Object.entries(OPS).map(([k, v]) => [v, k]));
const used = [...new Set(ops.fnArray)].map((n) => names[n]);
console.log("ops used:", used.join(", "));
const imgs = await extractImages(pdf, 1);
console.log("images:", imgs.length, imgs.map((i) => ({ w: i.width, h: i.height, ch: i.channels, key: i.key })));
