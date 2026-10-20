# 02 · Nhân viên AI thử việc: hỏi database bằng tiếng Việt (Text-to-SQL)

**SQL chạy được nhưng số sai: thử thách 30 câu, 5 cấp độ, 4 power-up, 3 model.**

📺 Video (tiếng Việt): https://youtu.be/9gzg9k_u6J4

## Thí nghiệm

- **Database:** chuỗi trà sữa giả lập "Trà Sữa Mây" (`make_db.py`, SQLite, mọi dữ liệu đều là dữ liệu bịa).
  - 6 chi nhánh, 600 khách, 4.011 đơn hàng từ tháng 1 đến tháng 9/2026.
  - 6 bảng bán hàng và 26 bảng "nhiễu" (kho, lương, quảng cáo…), tổng cộng 32 bảng.
  - Cài sẵn các quy tắc nghiệp vụ: doanh thu chỉ tính đơn `completed`; "số ly" là `SUM(quantity)`; giá khách trả (`unit_price`) có thể khác giá niêm yết.
- **30 câu hỏi tiếng Việt, 5 cấp độ** (`questions.py`), mỗi câu có một SQL đáp án viết tay:

  | Level | Nội dung |
  |---|---|
  | 1 | Đếm, lọc |
  | 2 | Nối bảng |
  | 3 | Thời gian |
  | 4 | Quy tắc nghiệp vụ |
  | 5 | Nhiều bước |

- **Chấm điểm tự động:** chạy SQL của AI và SQL đáp án rồi so kết quả. Mỗi cột của đáp án phải xuất hiện trong kết quả của AI với cùng giá trị, và số dòng phải bằng nhau.
- **5 mức power-up cộng dồn**, theo thứ tự trong notebook Text-to-SQL của Claude Cookbooks:

  | Mức | Thêm gì |
  |---|---|
  | `base` | Schema 32 bảng + câu hỏi |
  | `examples` | 3 dòng dữ liệu mẫu mỗi bảng + 3 câu hỏi mẫu có SQL đúng |
  | `thinking` | Yêu cầu suy nghĩ từng bước trong `<thinking>` |
  | `rag` | Chỉ đưa 5 bảng khớp nhất (BM25 trên mô tả tiếng Việt của từng bảng) |
  | `fix` | Chạy SQL, đưa lỗi hoặc kết quả lại cho AI tự sửa (tối đa 2 vòng) |

- **3 model trên Groq**, temperature 0: GPT-OSS 120B, GPT-OSS 20B, Qwen 3.6 27B.

## Kết quả (điểm trên 30)

| model | base | +examples | +thinking | +rag | +fix |
|---|---|---|---|---|---|
| GPT-OSS 120B | 22 | **28** | 28 | 28 | 27 |
| GPT-OSS 20B | 22 | 23 | **26** | 25 | 25 |
| Qwen 3.6 27B | 22 | **28** | 28 | 27 | 27 |

Những gì đọc được từ các câu sai (xem SQL thật trong `results/results.json`):

- **Lỗi im lặng:** ở mức `base`, GPT-OSS 120B sai 8 câu và **cả 8 đều không báo lỗi gì**.
  - Doanh thu tháng 8 báo 36,4 triệu, đúng là 32,8 triệu, vì cộng cả đơn huỷ và hoàn tiền.
  - Model tìm `role = 'manager'` trong khi dữ liệu ghi `'quản lý'`.
  - Model viết `'canceled'` trong khi dữ liệu ghi `'cancelled'`.
- **Ví dụ mẫu** là bước nhảy lớn nhất ở 2/3 model (+6 điểm), nhưng lại làm sai câu "khách đăng ký thành viên": model lọc thêm `tier = 'member'`.
- **Dịch từng chữ:** hỏi khách hạng "vàng" thì model viết `tier = 'vàng'` thay vì `'gold'`.
- **RAG** có lúc chọn bảng chấm công `timesheets` thay vì bảng `orders`. RAG chưa làm tăng điểm ở model nào.
- **Tự sửa lỗi chưa cứu thêm được câu nào ở model nào**:
  - GPT-OSS 120B sửa một đáp án đúng (`'gold'`) thành sai (`'vàng'`).
  - Ở câu khác, nó bọc truy vấn bằng `COALESCE` để kết quả rỗng trông như có số liệu.

## Tự chạy

```bash
pip install -r requirements.txt
python make_db.py                        # tạo data/trasua.db
# .env cạnh experiment.py: GROQ_API_KEY=...   (miễn phí tại console.groq.com)
python experiment.py                     # dùng cache có sẵn trong results/cache: không gọi API
python experiment.py --models gpt-oss-120b --stages base examples
```

Các câu trả lời của model đã được cache trong `results/cache/`, nên chạy lại cho ra đúng số trên mà không tốn tiền. Muốn gọi model thật thì xoá thư mục cache.

## Bài học

1. Cho AI xem dữ liệu mẫu và vài câu hỏi mẫu có đáp án.
2. Viết ra quy tắc nghiệp vụ: doanh thu là gì, số ly là gì, đơn nào được tính.
3. Đừng tin kết quả rỗng, 0 hay NULL. Kiểm tra bằng code, đừng để AI tự chấm bài.
4. Giữ một bộ câu hỏi có đáp án và chạy lại mỗi khi đổi prompt hay đổi model.

## Nguồn

Ý tưởng từ Anthropic **Claude Cookbooks** (giấy phép MIT), notebook
[`capabilities/text_to_sql/guide.ipynb`](https://github.com/anthropics/claude-cookbooks/blob/main/capabilities/text_to_sql/guide.ipynb).
Database, câu hỏi, code và số liệu ở đây do mình tự tạo và tự chạy, không dùng model Claude.
