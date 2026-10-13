interface Props {
  total: number;
  shown: number;
  expanded: boolean;
  onToggle: () => void;
  unit: string; // "本", "個"
}

/** "もっと見る（あと n 本）" / "たたむ" under a list that is cut short on phones. */
export function ShowMore({ total, shown, expanded, onToggle, unit }: Props) {
  if (!expanded && shown >= total) return null;
  return (
    <button className="link-button show-more" onClick={onToggle}>
      {expanded ? "たたむ" : `もっと見る（あと ${total - shown} ${unit}）`}
    </button>
  );
}
