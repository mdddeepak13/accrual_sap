/**
 * Parse a Marp-style markdown deck into an array of slide bodies.
 *
 * Format assumption: file starts with YAML frontmatter bounded by
 * `---` lines, then one or more slides separated by `---` lines.
 */
export function parseSlides(markdown: string): string[] {
  const lines = markdown.split("\n");

  // Skip the opening YAML frontmatter.
  let startIndex = 0;
  if (lines[0]?.trim() === "---") {
    for (let i = 1; i < lines.length; i++) {
      if (lines[i].trim() === "---") {
        startIndex = i + 1;
        break;
      }
    }
  }

  // Split remaining lines on bare `---` delimiters.
  const slides: string[] = [];
  let buffer: string[] = [];
  for (let i = startIndex; i < lines.length; i++) {
    if (lines[i].trim() === "---") {
      const body = buffer.join("\n").trim();
      if (body) slides.push(body);
      buffer = [];
    } else {
      buffer.push(lines[i]);
    }
  }
  const tail = buffer.join("\n").trim();
  if (tail) slides.push(tail);

  return slides;
}
