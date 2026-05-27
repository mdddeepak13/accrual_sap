interface Props {
  /** Pixel height; width scales by the source file's aspect ratio. */
  size?: number;
  className?: string;
}

/**
 * Renders the official TCS logo from /public/tcs-logo.svg.
 *
 * Drop the file at `web/public/tcs-logo.svg` (preferred) or
 * `web/public/tcs-logo.png`. Next.js serves anything under /public/
 * statically; this component just references it by path so we don't
 * embed any brand artwork in the repo source.
 */
export function TcsLogo({ size = 24, className = "" }: Props) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/TCS-logo-black-CMYK.svg"
      alt="Tata Consultancy Services"
      height={size}
      style={{ height: size, width: "auto" }}
      className={className}
    />
  );
}
