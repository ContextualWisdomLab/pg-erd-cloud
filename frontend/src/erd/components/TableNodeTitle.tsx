type Badges = {
  pk?: boolean;
  fk?: boolean;
};

type BusinessGroup = {
  id: string;
  name: string;
  color: string;
};

export function TableNodeTitle({
  title,
  comment,
  businessGroup,
  badges,
}: {
  title: string;
  comment?: string | null;
  businessGroup?: BusinessGroup | null;
  badges?: Badges;
}) {
  return (
    <div className="tableNode__title">
      <span className="tableNode__titleText">
        <span>{title}</span>
        {comment ? (
          <span className="tableNode__titleComment">{comment}</span>
        ) : null}
      </span>
      <span style={{ display: "inline-flex", gap: 6 }}>
        {businessGroup ? (
          <span className="tableNode__groupBadge">{businessGroup.name}</span>
        ) : null}
        {badges?.pk ? <span className="tableNode__badge">PK</span> : null}
        {badges?.fk ? <span className="tableNode__badge">FK</span> : null}
      </span>
    </div>
  );
}
