import { useState } from "react";

interface Props {
  src: string | null;
  width: number;
  height: number;
  label?: string;
}

/** Header image that falls back to an empty frame when missing or broken. */
export function GameImage({ src, width, height, label }: Props) {
  const [broken, setBroken] = useState(false);
  if (!src || broken) return <span className="game-blank">{label}</span>;
  return <img src={src} alt="" width={width} height={height} loading="lazy" onError={() => setBroken(true)} />;
}
