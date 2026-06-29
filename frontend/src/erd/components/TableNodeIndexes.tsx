type Index = {
  index_name: string;
  columns: string[];
  access_method: string;
  strength?: string;
};

export function TableNodeIndexes({ indexes }: { indexes: Index[] }) {
  if (!indexes || !indexes.length) return null;

  return (
    <div className="tableNode__indexes" role="group" aria-label="추천 인덱스">
      <div className="tableNode__indexHeading">Indexes</div>
      {indexes.slice(0, 4).map((index) => (
        <div key={index.index_name} className="tableNode__index">
          <span className="tableNode__indexName">{index.index_name}</span>
          <span className="tableNode__indexCols">
            ({index.columns.join(", ")})
          </span>
        </div>
      ))}
      {indexes.length > 4 ? (
        <div className="tableNode__more">
          … {indexes.length - 4} more indexes
        </div>
      ) : null}
    </div>
  );
}
