"""30 Vietnamese business questions in 5 levels, each with a hand-written gold SQL query.

A model answer is correct when its result matches the gold result (see grade.py): every gold column must
appear among the model's columns with the same values, and the number of rows must match.
"""
Q = [
    # ---- Level 1: one table, plain filters and counts --------------------------------------------------
    (1, "Chuỗi có bao nhiêu chi nhánh?",
     "SELECT COUNT(*) FROM branches"),
    (1, "Liệt kê tên các chi nhánh ở Hà Nội.",
     "SELECT name FROM branches WHERE city = 'Hà Nội'"),
    (1, "Món nào có giá niêm yết cao nhất?",
     "SELECT name FROM products ORDER BY price DESC LIMIT 1"),
    (1, "Có bao nhiêu món thuộc nhóm trà trái cây?",
     "SELECT COUNT(*) FROM products WHERE category = 'trà trái cây'"),
    (1, "Có bao nhiêu đơn hàng bị huỷ?",
     "SELECT COUNT(*) FROM orders WHERE status = 'cancelled'"),
    (1, "Có bao nhiêu khách hàng hạng vàng?",
     "SELECT COUNT(*) FROM customers WHERE tier = 'gold'"),
    # ---- Level 2: joins and grouping --------------------------------------------------------------------
    (2, "Chi nhánh nào có nhiều đơn hàng hoàn thành nhất?",
     "SELECT b.name FROM orders o JOIN branches b ON b.id = o.branch_id WHERE o.status = 'completed' "
     "GROUP BY b.id ORDER BY COUNT(*) DESC LIMIT 1"),
    (2, "Mỗi thành phố có bao nhiêu khách hàng?",
     "SELECT city, COUNT(*) FROM customers GROUP BY city"),
    (2, "Quản lý của chi nhánh Mây Thảo Điền tên là gì?",
     "SELECT s.full_name FROM staff s JOIN branches b ON b.id = s.branch_id "
     "WHERE b.name = 'Mây Thảo Điền' AND s.role = 'quản lý'"),
    (2, "Mỗi kênh bán hàng có bao nhiêu đơn hàng?",
     "SELECT channel, COUNT(*) FROM orders GROUP BY channel"),
    (2, "Món nào đã ngừng bán?",
     "SELECT name FROM products WHERE is_active = 0"),
    (2, "Chi nhánh Mây Hải Châu có bao nhiêu nhân viên pha chế?",
     "SELECT COUNT(*) FROM staff s JOIN branches b ON b.id = s.branch_id "
     "WHERE b.name = 'Mây Hải Châu' AND s.role = 'pha chế'"),
    # ---- Level 3: dates and time comparisons ------------------------------------------------------------
    (3, "Tháng nào trong năm 2026 có nhiều đơn hàng hoàn thành nhất?",
     "SELECT CAST(strftime('%m', ordered_at) AS INTEGER) FROM orders WHERE status = 'completed' "
     "AND ordered_at >= '2026-01-01' GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1"),
    (3, "Có bao nhiêu đơn hàng hoàn thành trong quý 2 năm 2026?",
     "SELECT COUNT(*) FROM orders WHERE status = 'completed' AND ordered_at >= '2026-04-01' "
     "AND ordered_at < '2026-07-01'"),
    (3, "Chi nhánh Mây Cầu Giấy nhận đơn hàng đầu tiên vào ngày nào?",
     "SELECT MIN(date(o.ordered_at)) FROM orders o JOIN branches b ON b.id = o.branch_id "
     "WHERE b.name = 'Mây Cầu Giấy'"),
    (3, "Số đơn hàng hoàn thành tháng 9/2026 nhiều hơn tháng 8/2026 bao nhiêu đơn (số âm nếu giảm)?",
     "SELECT SUM(ordered_at >= '2026-09-01' AND ordered_at < '2026-10-01') "
     "- SUM(ordered_at >= '2026-08-01' AND ordered_at < '2026-09-01') FROM orders WHERE status = 'completed'"),
    (3, "Có bao nhiêu khách hàng đăng ký thành viên trong năm 2026?",
     "SELECT COUNT(*) FROM customers WHERE joined_at >= '2026-01-01' AND joined_at < '2027-01-01'"),
    (3, "Giờ nào trong ngày có nhiều đơn hàng nhất?",
     "SELECT CAST(strftime('%H', ordered_at) AS INTEGER) FROM orders GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1"),
    # ---- Level 4: business rules (revenue, cups, real price paid, walk-in customers) --------------------
    (4, "Tổng doanh thu tháng 8/2026 là bao nhiêu?",
     "SELECT SUM(i.quantity * i.unit_price) FROM order_items i JOIN orders o ON o.id = i.order_id "
     "WHERE o.status = 'completed' AND o.ordered_at >= '2026-08-01' AND o.ordered_at < '2026-09-01'"),
    (4, "Năm 2026 chuỗi bán được tổng cộng bao nhiêu ly Trà sữa trân châu?",
     "SELECT SUM(i.quantity) FROM order_items i JOIN orders o ON o.id = i.order_id JOIN products p ON p.id = i.product_id "
     "WHERE o.status = 'completed' AND p.name = 'Trà sữa trân châu'"),
    (4, "Doanh thu từ khách hàng hạng vàng trong tháng 7/2026 là bao nhiêu?",
     "SELECT SUM(i.quantity * i.unit_price) FROM order_items i JOIN orders o ON o.id = i.order_id "
     "JOIN customers c ON c.id = o.customer_id WHERE o.status = 'completed' AND c.tier = 'gold' "
     "AND o.ordered_at >= '2026-07-01' AND o.ordered_at < '2026-08-01'"),
    (4, "Trong tháng 8/2026, khách thực trả trung bình bao nhiêu tiền cho một ly Trà đào cam sả size M?",
     "SELECT AVG(i.unit_price) FROM order_items i JOIN orders o ON o.id = i.order_id "
     "JOIN products p ON p.id = i.product_id WHERE p.name = 'Trà đào cam sả' AND i.size = 'M' "
     "AND o.status = 'completed' AND o.ordered_at >= '2026-08-01' AND o.ordered_at < '2026-09-01'"),
    (4, "Bao nhiêu phần trăm đơn hàng qua kênh grab bị huỷ hoặc hoàn tiền?",
     "SELECT 100.0 * SUM(status IN ('cancelled', 'refunded')) / COUNT(*) FROM orders WHERE channel = 'grab'"),
    (4, "Có bao nhiêu đơn hàng hoàn thành của khách vãng lai (không có tài khoản thành viên)?",
     "SELECT COUNT(*) FROM orders WHERE customer_id IS NULL AND status = 'completed'"),
    # ---- Level 5: several steps in one question ---------------------------------------------------------
    (5, "Với mỗi chi nhánh, món nào bán được nhiều ly nhất?",
     "SELECT branch, product FROM (SELECT b.name AS branch, p.name AS product, "
     "RANK() OVER (PARTITION BY b.id ORDER BY SUM(i.quantity) DESC) AS r FROM order_items i "
     "JOIN orders o ON o.id = i.order_id JOIN branches b ON b.id = o.branch_id JOIN products p ON p.id = i.product_id "
     "WHERE o.status = 'completed' GROUP BY b.id, p.id) WHERE r = 1"),
    (5, "Ba khách hàng chi tiêu nhiều nhất năm 2026 là ai?",
     "SELECT c.full_name FROM order_items i JOIN orders o ON o.id = i.order_id JOIN customers c ON c.id = o.customer_id "
     "WHERE o.status = 'completed' GROUP BY c.id ORDER BY SUM(i.quantity * i.unit_price) DESC LIMIT 3"),
    (5, "Chi nhánh nào có doanh thu tháng 9/2026 tăng mạnh nhất (theo phần trăm) so với tháng 8/2026?",
     "WITH m AS (SELECT o.branch_id, SUM(CASE WHEN o.ordered_at >= '2026-09-01' THEN i.quantity * i.unit_price END) AS sep, "
     "SUM(CASE WHEN o.ordered_at < '2026-09-01' THEN i.quantity * i.unit_price END) AS aug FROM order_items i "
     "JOIN orders o ON o.id = i.order_id WHERE o.status = 'completed' AND o.ordered_at >= '2026-08-01' "
     "AND o.ordered_at < '2026-10-01' GROUP BY o.branch_id) "
     "SELECT b.name FROM m JOIN branches b ON b.id = m.branch_id ORDER BY 1.0 * (sep - aug) / aug DESC LIMIT 1"),
    (5, "Trong số khách hàng có ít nhất một đơn hoàn thành năm 2026, bao nhiêu phần trăm có từ 2 đơn hoàn thành trở lên?",
     "SELECT 100.0 * SUM(n >= 2) / COUNT(*) FROM (SELECT customer_id, COUNT(*) AS n FROM orders "
     "WHERE status = 'completed' AND customer_id IS NOT NULL GROUP BY customer_id)"),
    (5, "Nhân viên thu ngân nào xử lý nhiều đơn hàng hoàn thành nhất?",
     "SELECT s.full_name FROM orders o JOIN staff s ON s.id = o.staff_id WHERE s.role = 'thu ngân' "
     "AND o.status = 'completed' GROUP BY s.id ORDER BY COUNT(*) DESC LIMIT 1"),
    (5, "Giá trị trung bình của một đơn hàng hoàn thành ở mỗi kênh bán là bao nhiêu?",
     "SELECT channel, AVG(total) FROM (SELECT o.id, o.channel, SUM(i.quantity * i.unit_price) AS total "
     "FROM orders o JOIN order_items i ON i.order_id = o.id WHERE o.status = 'completed' GROUP BY o.id) GROUP BY channel"),
]
