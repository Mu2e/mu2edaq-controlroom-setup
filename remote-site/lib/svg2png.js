// svg2png.js -- draw an SVG into a transparent PNG with AppKit (macOS only).
// Usage: osascript -l JavaScript svg2png.js SRC.svg DST.png SIZE
// Used by remote-site/install.sh for the macOS launcher icons; needs
// nothing beyond macOS itself.
ObjC.import('AppKit');
function run(argv) {
  const [src, dst, size] = [argv[0], argv[1], parseInt(argv[2])];
  const img = $.NSImage.alloc.initWithContentsOfFile(src);
  if (img.isNil()) throw new Error('cannot read ' + src);
  const rep = $.NSBitmapImageRep.alloc.initWithBitmapDataPlanesPixelsWidePixelsHighBitsPerSampleSamplesPerPixelHasAlphaIsPlanarColorSpaceNameBytesPerRowBitsPerPixel(
      null, size, size, 8, 4, true, false, $.NSDeviceRGBColorSpace, 0, 0);
  rep.size = $.NSMakeSize(size, size);
  $.NSGraphicsContext.saveGraphicsState;
  $.NSGraphicsContext.setCurrentContext($.NSGraphicsContext.graphicsContextWithBitmapImageRep(rep));
  img.drawInRectFromRectOperationFraction($.NSMakeRect(0, 0, size, size), $.NSZeroRect, $.NSCompositingOperationSourceOver, 1.0);
  $.NSGraphicsContext.restoreGraphicsState;
  const png = rep.representationUsingTypeProperties($.NSBitmapImageFileTypePNG, $());
  if (!png.writeToFileAtomically(dst, true)) throw new Error('cannot write ' + dst);
}
