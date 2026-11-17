CREATE SCHEMA sales_demo;

CREATE TABLE sales_demo.customers (
    customer_id integer PRIMARY KEY,
    name text NOT NULL,
    region text NOT NULL
);
CREATE TABLE sales_demo.products (
    product_id integer PRIMARY KEY,
    name text NOT NULL,
    category text NOT NULL,
    unit_price numeric(12,2) NOT NULL CHECK (unit_price >= 0)
);
CREATE TABLE sales_demo.orders (
    order_id integer PRIMARY KEY,
    customer_id integer NOT NULL REFERENCES sales_demo.customers,
    order_date date NOT NULL,
    status text NOT NULL CHECK (status IN ('completed', 'pending', 'cancelled'))
);
CREATE TABLE sales_demo.order_items (
    order_id integer NOT NULL REFERENCES sales_demo.orders,
    product_id integer NOT NULL REFERENCES sales_demo.products,
    quantity integer NOT NULL CHECK (quantity > 0),
    unit_price numeric(12,2) NOT NULL CHECK (unit_price >= 0),
    PRIMARY KEY (order_id, product_id)
);

INSERT INTO sales_demo.customers VALUES
    (1, 'Demo Customer A', 'North'),
    (2, 'Demo Customer B', 'South'),
    (3, 'Demo Customer C', 'West');
INSERT INTO sales_demo.products VALUES
    (1, 'Widget', 'Accessories', 25.00),
    (2, 'Keyboard', 'Accessories', 50.00),
    (3, 'Monitor', 'Displays', 200.00);
INSERT INTO sales_demo.orders VALUES
    (1, 1, '2026-01-05', 'completed'),
    (2, 2, '2026-01-15', 'completed'),
    (3, 3, '2026-02-03', 'completed'),
    (4, 1, '2026-02-18', 'completed'),
    (5, 2, '2026-02-20', 'cancelled'),
    (6, 3, '2026-02-25', 'pending');
-- Store the actual sale price, independently of future product price changes.
INSERT INTO sales_demo.order_items VALUES
    (1, 2, 2, 50.00),
    (2, 1, 2, 25.00), (2, 2, 2, 50.00),
    (3, 3, 1, 200.00),
    (4, 3, 1, 200.00), (4, 2, 1, 50.00),
    (5, 3, 2, 200.00),
    (6, 1, 4, 25.00);
