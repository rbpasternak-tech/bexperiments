/**
 * pdf-processor.js — Read PDF text via PDF.js, write via pdf-lib.
 * Handles text extraction, clean replacement (rebuilds as new PDF),
 * and redline generation (strikethrough + colored text).
 */

import { escapeRegex } from './replacer.js';

/* global pdfjsLib, PDFLib */

// Configure PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

/**
 * Reads a PDF ArrayBuffer and extracts all text content.
 * @param {ArrayBuffer} data - The PDF file as an ArrayBuffer.
 * @returns {Promise<string>} The extracted plain text.
 */
export async function readPdfText(data) {
  const pdf = await pdfjsLib.getDocument({ data }).promise;
  const textParts = [];

  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    const pageText = content.items.map((item) => item.str).join(' ');
    textParts.push(pageText);
  }

  return textParts.join('\n');
}

/**
 * Extracts text from each page of a PDF separately.
 * @param {ArrayBuffer} data - The PDF file as an ArrayBuffer.
 * @returns {Promise<Array<string>>} Array of text strings, one per page.
 */
export async function readPdfTextByPage(data) {
  const pdf = await pdfjsLib.getDocument({ data }).promise;
  const pages = [];

  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    const pageText = content.items.map((item) => item.str).join(' ');
    pages.push(pageText);
  }

  return pages;
}

/**
 * Applies clean replacements to a PDF and returns a new PDF ArrayBuffer.
 * Rebuilds the PDF with Helvetica font; original formatting is not preserved.
 * @param {ArrayBuffer} data - Original PDF ArrayBuffer.
 * @param {Array<{find: string, replace: string, isBracket: boolean}>} replacements - Replacement operations.
 * @returns {Promise<ArrayBuffer>} The modified PDF as ArrayBuffer.
 */
export async function applyPdfCleanReplacements(data, replacements) {
  const pageTexts = await readPdfTextByPage(data);
  const pdfDoc = await PDFLib.PDFDocument.create();
  const font = await pdfDoc.embedFont(PDFLib.StandardFonts.Helvetica);
  const fontSize = 11;
  const margin = 50;
  const lineHeight = fontSize * 1.4;

  for (let i = 0; i < pageTexts.length; i++) {
    let text = pageTexts[i];

    for (const r of replacements) {
      if (r.replace === undefined || r.replace === null) continue;
      let pattern;
      if (r.isBracket) {
        pattern = new RegExp('\\[' + escapeRegex(r.find) + '\\]', 'gi');
      } else {
        pattern = new RegExp('\\b' + escapeRegex(r.find) + '\\b', 'gi');
      }
      text = text.replace(pattern, r.replace);
    }

    const page = pdfDoc.addPage([612, 792]); // US Letter
    const { width, height } = page.getSize();
    const maxWidth = width - margin * 2;
    const lines = wrapText(text, font, fontSize, maxWidth);

    let y = height - margin;
    for (const line of lines) {
      if (y < margin) {
        // Overflow: add a new page
        const newPage = pdfDoc.addPage([612, 792]);
        y = newPage.getSize().height - margin;
        newPage.drawText(line, {
          x: margin,
          y,
          size: fontSize,
          font,
          color: PDFLib.rgb(0, 0, 0)
        });
      } else {
        page.drawText(line, {
          x: margin,
          y,
          size: fontSize,
          font,
          color: PDFLib.rgb(0, 0, 0)
        });
      }
      y -= lineHeight;
    }
  }

  return pdfDoc.save();
}

/**
 * Creates a redline PDF showing old text struck through in red
 * and new text in green.
 * @param {ArrayBuffer} data - Original PDF ArrayBuffer.
 * @param {Array<{find: string, replace: string, isBracket: boolean}>} replacements - Replacement operations.
 * @returns {Promise<ArrayBuffer>} The redline PDF as ArrayBuffer.
 */
export async function applyPdfRedlineReplacements(data, replacements) {
  const pageTexts = await readPdfTextByPage(data);
  const pdfDoc = await PDFLib.PDFDocument.create();
  const font = await pdfDoc.embedFont(PDFLib.StandardFonts.Helvetica);
  const fontSize = 11;
  const margin = 50;
  const lineHeight = fontSize * 1.6;

  for (let i = 0; i < pageTexts.length; i++) {
    const originalText = pageTexts[i];

    // Find all matches and build segments
    const segments = buildRedlineSegments(originalText, replacements);

    const page = pdfDoc.addPage([612, 792]);
    const { width, height } = page.getSize();
    const maxWidth = width - margin * 2;
    let x = margin;
    let y = height - margin;

    for (const seg of segments) {
      if (seg.type === 'unchanged') {
        // Draw in black
        const lines = wrapText(seg.text, font, fontSize, maxWidth - (x - margin));
        for (let li = 0; li < lines.length; li++) {
          if (y < margin) {
            const newPage = pdfDoc.addPage([612, 792]);
            y = newPage.getSize().height - margin;
            x = margin;
          }
          if (li > 0) { x = margin; y -= lineHeight; }
          page.drawText(lines[li], {
            x, y, size: fontSize, font,
            color: PDFLib.rgb(0, 0, 0)
          });
          x += font.widthOfTextAtSize(lines[li], fontSize);
        }
      } else if (seg.type === 'deleted') {
        // Draw in red with strikethrough effect
        const textWidth = font.widthOfTextAtSize(seg.text, fontSize);
        if (x + textWidth > margin + maxWidth) {
          y -= lineHeight;
          x = margin;
        }
        if (y < margin) {
          pdfDoc.addPage([612, 792]);
          y = 792 - margin;
          x = margin;
        }
        page.drawText(seg.text, {
          x, y, size: fontSize, font,
          color: PDFLib.rgb(0.8, 0, 0)
        });
        // Draw strikethrough line
        page.drawLine({
          start: { x, y: y + fontSize * 0.35 },
          end: { x: x + textWidth, y: y + fontSize * 0.35 },
          thickness: 1,
          color: PDFLib.rgb(0.8, 0, 0)
        });
        x += textWidth;
      } else if (seg.type === 'inserted') {
        // Draw in green
        const textWidth = font.widthOfTextAtSize(seg.text, fontSize);
        if (x + textWidth > margin + maxWidth) {
          y -= lineHeight;
          x = margin;
        }
        if (y < margin) {
          pdfDoc.addPage([612, 792]);
          y = 792 - margin;
          x = margin;
        }
        page.drawText(seg.text, {
          x, y, size: fontSize, font,
          color: PDFLib.rgb(0, 0.6, 0)
        });
        x += textWidth;
      }
    }
  }

  return pdfDoc.save();
}

/**
 * Builds segments for redline display: unchanged text, deleted text, inserted text.
 * @param {string} text - The original text.
 * @param {Array<{find: string, replace: string, isBracket: boolean}>} replacements - Replacement operations.
 * @returns {Array<{type: string, text: string}>} Segments array.
 */
function buildRedlineSegments(text, replacements) {
  // Collect all matches
  const allMatches = [];
  for (const r of replacements) {
    if (r.replace === undefined || r.replace === null) continue;
    let pattern;
    if (r.isBracket) {
      pattern = new RegExp('\\[' + escapeRegex(r.find) + '\\]', 'gi');
    } else {
      pattern = new RegExp('\\b' + escapeRegex(r.find) + '\\b', 'gi');
    }
    let m;
    while ((m = pattern.exec(text)) !== null) {
      allMatches.push({
        start: m.index,
        end: m.index + m[0].length,
        original: m[0],
        replacement: r.replace
      });
    }
  }

  if (allMatches.length === 0) {
    return [{ type: 'unchanged', text }];
  }

  allMatches.sort((a, b) => a.start - b.start);

  const segments = [];
  let cursor = 0;

  for (const match of allMatches) {
    if (match.start < cursor) continue; // Skip overlapping

    if (cursor < match.start) {
      segments.push({ type: 'unchanged', text: text.substring(cursor, match.start) });
    }
    segments.push({ type: 'deleted', text: match.original });
    segments.push({ type: 'inserted', text: match.replacement });
    cursor = match.end;
  }

  if (cursor < text.length) {
    segments.push({ type: 'unchanged', text: text.substring(cursor) });
  }

  return segments;
}

/**
 * Wraps text into lines that fit within maxWidth at the given font and size.
 * @param {string} text - The text to wrap.
 * @param {Object} font - The pdf-lib font object.
 * @param {number} fontSize - Font size in points.
 * @param {number} maxWidth - Maximum line width in points.
 * @returns {Array<string>} Array of wrapped lines.
 */
function wrapText(text, font, fontSize, maxWidth) {
  if (!text) return [''];
  const words = text.split(/\s+/);
  const lines = [];
  let currentLine = '';

  for (const word of words) {
    if (!word) continue;
    const testLine = currentLine ? currentLine + ' ' + word : word;
    const testWidth = font.widthOfTextAtSize(testLine, fontSize);

    if (testWidth > maxWidth && currentLine) {
      lines.push(currentLine);
      currentLine = word;
    } else {
      currentLine = testLine;
    }
  }

  if (currentLine) {
    lines.push(currentLine);
  }

  return lines.length > 0 ? lines : [''];
}
