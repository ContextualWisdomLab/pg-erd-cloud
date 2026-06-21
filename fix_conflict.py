import re

with open('backend/tests/test_ddl_export.py', 'r') as f:
    content = f.read()

content = content.replace('CREATE INDEX events_id_idx ON public.events USING btree (id) TABLESPACE "fast_space";', 'CREATE INDEX CONCURRENTLY events_id_idx ON public.events USING btree (id) TABLESPACE "fast_space";')

with open('backend/tests/test_ddl_export.py', 'w') as f:
    f.write(content)
