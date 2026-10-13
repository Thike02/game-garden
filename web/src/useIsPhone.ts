import { useEffect, useState } from "react";

const QUERY = "(max-width: 600px)"; // same breakpoint as the phone rules in styles.css

/** True on phone-width screens; updates when the window is resized or rotated. */
export function useIsPhone(): boolean {
  const [isPhone, setIsPhone] = useState(() => window.matchMedia(QUERY).matches);
  useEffect(() => {
    const media = window.matchMedia(QUERY);
    const update = () => setIsPhone(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return isPhone;
}
