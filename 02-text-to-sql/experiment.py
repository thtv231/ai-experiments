"""Text-to-SQL challenge: 30 Vietnamese questions, 5 levels, 5 cumulative power-ups, 3 models.

  python make_db.py                      # once: build data/trasua.db
  python experiment.py                   # run everything (cached), print the score table, write results/results.json
  python experiment.py --models gpt-oss-120b --stages base examples

Power-ups (each stage keeps everything from the previous one), following the order of Anthropic's
Claude Cookbooks notebook capabilities/text_to_sql:
  base       schema of all 32 tables + the question
  examples   + 3 sample rows per table and 3 worked question → SQL examples
  thinking   + "think step by step in <thinking> before writing the SQL"
  rag        only the 5 tables whose descriptions best match the question (BM25), instead of all 32
  fix        run the SQL; show the error or the first rows back to the model, let it correct itself (2 rounds)

Keys from .env next to this script: GROQ_API_KEY (free at console.groq.com).
Every model reply is cached in results/cache/, so a re-run costs nothing.
"""
import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from questions import Q

HERE = Path(__file__).resolve().parent
DB = HERE / "data" / "trasua.db"
CACHE = HERE / "results" / "cache"
STAGES = ["base", "examples", "thinking", "rag", "fix"]
MODELS = {"gpt-oss-120b": "openai/gpt-oss-120b", "gpt-oss-20b": "openai/gpt-oss-20b", "qwen3.6-27b": "qwen/qwen3.6-27b"}

SYSTEM = """You are an expert data analyst who writes SQLite queries.
Given the database schema and a question in Vietnamese, write ONE SQLite query that answers it.
Return the query in a single ```sql code block."""

THINK = """Before writing the query, think step by step inside <thinking></thinking> tags: which tables and
columns you need, how they join, which filters the question implies, and what exactly to return."""

# worked examples (not in the test set)
EXAMPLES = """Examples:
Câu hỏi: Có bao nhiêu khách hàng ở Đà Nẵng?
```sql
SELECT COUNT(*) FROM customers WHERE city = 'Đà Nẵng';
```
Câu hỏi: Doanh thu tháng 3/2026 của chi nhánh Mây Nguyễn Huệ là bao nhiêu?
```sql
SELECT SUM(i.quantity * i.unit_price) FROM order_items i JOIN orders o ON o.id = i.order_id
JOIN branches b ON b.id = o.branch_id
WHERE b.name = 'Mây Nguyễn Huệ' AND o.status = 'completed'
  AND o.ordered_at >= '2026-03-01' AND o.ordered_at < '2026-04-01';
```
Câu hỏi: Bao nhiêu ly Bạc xỉu size L đã bán trong tháng 5/2026?
```sql
SELECT SUM(i.quantity) FROM order_items i JOIN orders o ON o.id = i.order_id
JOIN products p ON p.id = i.product_id
WHERE p.name = 'Bạc xỉu' AND i.size = 'L' AND o.status = 'completed'
  AND o.ordered_at >= '2026-05-01' AND o.ordered_at < '2026-06-01';
```"""

# short descriptions used to retrieve tables (Vietnamese, as the questions are)
TABLE_DOCS = {
    "branches": "chi nhánh cửa hàng tên thành phố ngày mở cửa",
    "products": "món đồ uống menu tên nhóm giá niêm yết đang bán ngừng bán",
    "customers": "khách hàng thành viên hạng vàng bạc thành phố ngày đăng ký",
    "staff": "nhân viên quản lý pha chế thu ngân chi nhánh",
    "orders": "đơn hàng thời gian đặt kênh bán trạng thái hoàn thành huỷ hoàn tiền khách vãng lai chi nhánh nhân viên",
    "order_items": "chi tiết đơn món số ly số lượng size giá thực trả doanh thu bán được",
    "suppliers": "nhà cung cấp nguyên liệu", "purchase_orders": "đơn mua hàng nhập nguyên liệu từ nhà cung cấp",
    "inventory": "tồn kho nguyên liệu", "inventory_moves": "xuất nhập kho", "ingredients": "nguyên liệu",
    "recipes": "công thức pha chế món", "equipment": "thiết bị máy móc", "maintenance_logs": "bảo trì thiết bị",
    "shifts": "ca làm việc", "timesheets": "chấm công giờ làm", "payroll": "bảng lương",
    "leave_requests": "đơn xin nghỉ phép", "promotions": "chương trình khuyến mãi giảm giá",
    "promotion_usage": "lượt dùng khuyến mãi", "marketing_campaigns": "chiến dịch marketing",
    "ad_spend": "chi phí quảng cáo", "social_posts": "bài đăng mạng xã hội", "reviews": "đánh giá của khách",
    "complaints": "khiếu nại của khách", "delivery_partners": "đối tác giao hàng",
    "delivery_fees": "phí giao hàng", "vouchers": "phiếu giảm giá voucher", "gift_cards": "thẻ quà tặng",
    "utilities_bills": "hoá đơn điện nước", "rent_contracts": "hợp đồng thuê mặt bằng",
    "audit_logs": "nhật ký thao tác hệ thống",
}


def schema(tables=None, samples=False):
    con = sqlite3.connect(DB)
    out = []
    for name, sql in con.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY rowid"):
        if tables and name not in tables:
            continue
        out.append(sql + ";")
        if samples:
            cur = con.execute(f"SELECT * FROM {name} LIMIT 3")
            rows = cur.fetchall()
            if rows:
                cols = [d[0] for d in cur.description]
                out.append(f"/* 3 sample rows of {name}:\n" + " | ".join(cols) + "\n" +
                           "\n".join(" | ".join(map(str, r)) for r in rows) + " */")
    return "\n".join(out)


def words(s):
    return re.findall(r"\w+", s.lower())


def retrieve(question, k=5):
    """BM25 over the table descriptions: the k tables that best match the question."""
    docs = {t: words(t.replace("_", " ") + " " + d) for t, d in TABLE_DOCS.items()}
    n, avg = len(docs), sum(map(len, docs.values())) / len(docs)
    df = Counter(w for d in docs.values() for w in set(d))
    q = words(question)
    def score(d):
        tf = Counter(d)
        return sum(math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5)) * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(d) / avg))
                   for w in q if w in tf)
    return sorted(docs, key=lambda t: -score(docs[t]))[:k]


def chat(model, messages):
    """One cached chat-completions call on Groq (temperature 0)."""
    request = {"model": MODELS[model], "messages": messages, "temperature": 0, "max_tokens": 8000, "seed": 0}
    if model.startswith("qwen"):
        request["reasoning_format"] = "hidden"
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24] + ".json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["reply"]
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1", max_retries=8)
    body = dict(request)
    extra = {"reasoning_format": body.pop("reasoning_format")} if "reasoning_format" in body else None
    reply = client.chat.completions.create(**body, **({"extra_body": extra} if extra else {})).choices[0].message.content or ""
    path.write_text(json.dumps({"request": request, "reply": reply}, ensure_ascii=False, indent=1), encoding="utf-8")
    return reply


def extract_sql(reply):
    reply = re.sub(r"<think(ing)?>.*?</think(ing)?>", "", reply, flags=re.S)
    m = re.findall(r"```(?:sql|sqlite)?\s*\n(.*?)```", reply, re.S)
    return (m[-1] if m else reply).strip().rstrip(";")


def run_sql(sql):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        cur = con.execute(sql)
        return cur.fetchmany(1000), None
    except Exception as e:                                     # syntax error, unknown column, ...
        return None, f"{type(e).__name__}: {e}"


def norm(v):
    if isinstance(v, float):
        return round(v, 1)
    if isinstance(v, str):
        return v.strip()
    return v


def grade(rows, gold):
    """Correct when the row counts match and every gold column appears among the answer's columns."""
    if rows is None or len(rows) != len(gold):
        return False
    if not gold:
        return True
    cols = list(zip(*rows)) if rows else []
    for g in zip(*gold):
        g = Counter(map(norm, g))
        if not any(Counter(map(norm, c)) == g for c in cols):
            # numbers: allow the model to round a little (e.g. 10.87 vs 10.9)
            ok = False
            for c in cols:
                try:
                    if all(math.isclose(float(a), float(b), rel_tol=0.005, abs_tol=0.051)
                           for a, b in zip(sorted(map(float, c)), sorted(map(float, g.elements())))):
                        ok = True
                        break
                except (TypeError, ValueError):
                    continue
            if not ok:
                return False
    return True


def solve(model, stage, question):
    """Answer one question with the power-ups of `stage` (and every earlier one). Returns a trace dict."""
    on = set(STAGES[:STAGES.index(stage) + 1])
    tables = retrieve(question) if "rag" in on else None
    system = SYSTEM + ("\n\n" + THINK if "thinking" in on else "")
    user = "Schema:\n" + schema(tables, samples="examples" in on)
    if "examples" in on:
        user += "\n\n" + EXAMPLES
    user += f"\n\nCâu hỏi: {question}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    reply = chat(model, messages)
    sql = extract_sql(reply)
    rows, err = run_sql(sql)
    rounds = 0
    while "fix" in on and rounds < 2:
        rounds += 1
        feedback = (f"Running your query gave an error:\n{err}" if err else
                    "Running your query returned " + (f"{len(rows)} rows. First rows:\n" + "\n".join(map(str, rows[:5]))
                                                      if rows else "no rows."))
        messages = messages + [{"role": "assistant", "content": reply},
                               {"role": "user", "content": feedback + "\n\nCheck carefully whether this result really "
                                "answers the question. If it does not, return a corrected query; if it does, return the "
                                "same query. Use one ```sql code block."}]
        reply = chat(model, messages)
        new = extract_sql(reply)
        if new == sql and not err:
            break
        sql = new
        rows, err = run_sql(sql)
    return {"sql": sql, "error": err, "rows": [list(r) for r in (rows or [])[:5]], "n_rows": len(rows or []),
            "tables": tables, "fix_rounds": rounds}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=list(MODELS))
    ap.add_argument("--stages", nargs="*", default=STAGES)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(HERE / ".env")
    except ImportError:
        pass
    gold = [run_sql(sql)[0] for _, _, sql in Q]
    jobs = [(m, s, k) for m in a.models for s in a.stages for k in range(len(Q))]

    def work(job):
        m, s, k = job
        t = solve(m, s, Q[k][1])
        rows, _ = run_sql(t["sql"]) if not t["error"] else (None, None)
        return {"model": m, "stage": s, "q": k + 1, "level": Q[k][0], "correct": grade(rows, gold[k]), **t}

    with ThreadPoolExecutor(a.workers) as ex:
        results = list(ex.map(work, jobs))
    print(f"{'model':13} {'stage':9} " + " ".join(f"L{l}" for l in range(1, 6)) + "  total")
    for m in a.models:
        for s in a.stages:
            r = [x for x in results if x["model"] == m and x["stage"] == s]
            per = [sum(x["correct"] for x in r if x["level"] == l) for l in range(1, 6)]
            print(f"{m:13} {s:9} " + " ".join(f"{p:2}" for p in per) + f"  {sum(per):2}/30")
    out = HERE / "results" / "results.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
