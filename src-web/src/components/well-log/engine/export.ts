import type { WellLogData } from '../types';

export async function svgToCanvas(svgEl: SVGSVGElement, scale: number): Promise<HTMLCanvasElement> {
  const cloned = svgEl.cloneNode(true) as SVGSVGElement;
  cloned.querySelectorAll('.interaction-layer').forEach(el => el.remove());
  const serializer = new XMLSerializer();
  const svgStr = serializer.serializeToString(cloned);
  const svgBlob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;
      const ctx = canvas.getContext('2d')!;
      ctx.scale(scale, scale);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, img.width, img.height);
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(url);
      resolve(canvas);
    };
    img.onerror = reject;
    img.src = url;
  });
}

export function doExportSVG(svgEl: SVGSVGElement, data: WellLogData, startDepth: number, endDepth: number) {
  const cloned = svgEl.cloneNode(true) as SVGSVGElement;
  cloned.querySelectorAll('.interaction-layer').forEach(el => el.remove());
  const svgStr = new XMLSerializer().serializeToString(cloned);
  const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
  const link = document.createElement('a');
  link.download = `${data.well_name}_${startDepth}-${endDepth}m.svg`;
  link.href = URL.createObjectURL(blob);
  link.click();
  URL.revokeObjectURL(link.href);
}

export async function doExportPNG(svgEl: SVGSVGElement, data: WellLogData, startDepth: number, endDepth: number) {
  const canvas = await svgToCanvas(svgEl, 3);
  const link = document.createElement('a');
  link.download = `${data.well_name}_${startDepth}-${endDepth}m.png`;
  link.href = canvas.toDataURL('image/png');
  link.click();
}

export function doExportPDF(svgEl: SVGSVGElement, data: WellLogData) {
  const cloned = svgEl.cloneNode(true) as SVGSVGElement;
  cloned.querySelectorAll('.interaction-layer').forEach(el => el.remove());
  const svgStr = new XMLSerializer().serializeToString(cloned);
  const win = window.open('', '_blank');
  if (!win) return;
  win.document.write(`<!DOCTYPE html><html><head><title>${data.well_name}</title>
    <style>
      @page { size: auto; margin: 10mm; }
      body { margin: 0; display: flex; justify-content: center; }
      svg { max-width: 100%; height: auto; }
    </style>
  </head><body>${svgStr}</body></html>`);
  win.document.close();
  win.onload = () => { win.print(); setTimeout(() => win.close(), 1000); };
}
