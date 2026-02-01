import { memo } from 'react'
import type { NodeProps } from '@xyflow/react'

type Column = {
  column_name: string
  data_type: string
  is_not_null: boolean
  is_pk?: boolean
}

function TableNode(props: NodeProps) {
  const data = props.data as { title: string; columns: Column[]; badges?: { pk?: boolean; fk?: boolean } }
  return (
    <div className="tableNode">
      <div className="tableNode__title">
        <span>{data.title}</span>
        <span style={{ display: 'inline-flex', gap: 6 }}>
          {data.badges?.pk ? <span className="tableNode__badge">PK</span> : null}
          {data.badges?.fk ? <span className="tableNode__badge">FK</span> : null}
        </span>
      </div>
      <div className="tableNode__cols">
        {data.columns.slice(0, 25).map((c) => (
          <div key={c.column_name} className="tableNode__col">
            <span className="tableNode__colName">{c.column_name}</span>
            <span className="tableNode__colType">{c.data_type}</span>
            {c.is_pk ? <span className="tableNode__badge">PK</span> : null}
            {c.is_not_null ? <span className="tableNode__badge">NOT NULL</span> : null}
          </div>
        ))}
        {data.columns.length > 25 ? <div className="tableNode__more">… {data.columns.length - 25} more</div> : null}
      </div>
    </div>
  )
}

export default memo(TableNode)
