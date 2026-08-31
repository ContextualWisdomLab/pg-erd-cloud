-- A small, real PostgreSQL target schema for the browser E2E path.
-- Each relation stores one fact type and non-key attributes depend on its key,
-- the whole key, and nothing but the key (3NF).

DROP SCHEMA IF EXISTS e2e_3nf CASCADE;
CREATE SCHEMA e2e_3nf;

CREATE TABLE e2e_3nf.order_status (
    order_status_code text PRIMARY KEY,
    status_name text NOT NULL UNIQUE
);

CREATE TABLE e2e_3nf.customer_account (
    customer_account_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE e2e_3nf.product_catalog (
    product_catalog_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_name text NOT NULL,
    current_unit_price numeric(12, 2) NOT NULL CHECK (current_unit_price >= 0)
);

CREATE TABLE e2e_3nf.sales_order (
    sales_order_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_account_id bigint NOT NULL,
    order_status_code text NOT NULL,
    ordered_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_sales_order_customer_account
        FOREIGN KEY (customer_account_id)
        REFERENCES e2e_3nf.customer_account (customer_account_id),
    CONSTRAINT fk_sales_order_order_status
        FOREIGN KEY (order_status_code)
        REFERENCES e2e_3nf.order_status (order_status_code)
);

CREATE TABLE e2e_3nf.sales_order_line (
    sales_order_line_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sales_order_id bigint NOT NULL,
    product_catalog_id bigint NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0),
    sold_unit_price numeric(12, 2) NOT NULL CHECK (sold_unit_price >= 0),
    CONSTRAINT fk_sales_order_line_sales_order
        FOREIGN KEY (sales_order_id)
        REFERENCES e2e_3nf.sales_order (sales_order_id),
    CONSTRAINT fk_sales_order_line_product_catalog
        FOREIGN KEY (product_catalog_id)
        REFERENCES e2e_3nf.product_catalog (product_catalog_id),
    CONSTRAINT uq_sales_order_line_order_product
        UNIQUE (sales_order_id, product_catalog_id)
);

CREATE INDEX ix_sales_order_customer_account
    ON e2e_3nf.sales_order (customer_account_id);
CREATE INDEX ix_sales_order_line_sales_order
    ON e2e_3nf.sales_order_line (sales_order_id);
CREATE INDEX ix_sales_order_line_product_catalog
    ON e2e_3nf.sales_order_line (product_catalog_id);

INSERT INTO e2e_3nf.order_status (order_status_code, status_name)
VALUES ('confirmed', 'Confirmed');

INSERT INTO e2e_3nf.customer_account (account_name)
VALUES ('Local 3NF Buyer');

INSERT INTO e2e_3nf.product_catalog (product_name, current_unit_price)
VALUES ('Normalized Widget', 19.95);

INSERT INTO e2e_3nf.sales_order (customer_account_id, order_status_code)
VALUES (1, 'confirmed');

INSERT INTO e2e_3nf.sales_order_line
    (sales_order_id, product_catalog_id, quantity, sold_unit_price)
VALUES (1, 1, 2, 19.95);

COMMENT ON SCHEMA e2e_3nf IS 'Local 3NF schema used by Playwright E2E';
COMMENT ON TABLE e2e_3nf.sales_order_line IS
    'Historical sold_unit_price is a line fact, not a product catalog attribute';
