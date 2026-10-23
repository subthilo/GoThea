// Texterkennung von macOS (Vision): eine Zeile je erkanntem Text, Tab-getrennt: x y Breite Höhe Text
// (Pixel, Ursprung oben links). Aufruf: swift scripts/ocr_labels.swift bild.png
// Genutzt von scripts/figure_tool.py, um die Beschriftungen einer Buchabbildung samt Lage zu lesen.
import AppKit
import Vision

let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let image = NSImage(contentsOf: url),
      let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
  FileHandle.standardError.write("Bild nicht lesbar\n".data(using: .utf8)!)
  exit(1)
}
let request = VNRecognizeTextRequest()
request.recognitionLanguages = ["de-DE"]
request.recognitionLevel = .accurate
try VNImageRequestHandler(cgImage: cg).perform([request])
let w = Double(cg.width), h = Double(cg.height)
for observation in request.results ?? [] {
  guard let text = observation.topCandidates(1).first else { continue }
  let b = observation.boundingBox
  print(String(format: "%d\t%d\t%d\t%d\t%@", Int(b.minX * w), Int((1 - b.maxY) * h), Int(b.width * w),
               Int(b.height * h), text.string))
}
