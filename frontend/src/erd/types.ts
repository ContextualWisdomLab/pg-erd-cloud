export type Column = {
  column_name: string;
  data_type: string;
  is_not_null: boolean;
  is_pk?: boolean;
  column_comment?: string | null;
  example_value?: string | number | boolean | null;
};

export type TableNodeData = {
  title: string;
  comment?: string | null;
  columns: Column[];
  businessGroup?: { id: string; name: string; color: string } | null;
  indexes?: Array<{
    index_name: string;
    columns: string[];
    access_method: string;
    strength?: string;
  }>;
  badges?: { pk?: boolean; fk?: boolean };
};
