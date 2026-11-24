# `semantic_service.py` —— **语义索引构建服务**
# 它和刚才的 `embedding_service.py` 配套：

# - ✅ 从 MySQL 读出商品、用户评价数据
# - ✅ 把每一条数据拼成一段描述文本
# - ✅ 分批调用 `embedding_service` 生成向量
# - ✅ 把【原文 + 向量 + 类型 + id】存成一个本地 JSON 文件 `semantic_index.json`

# 这个索引，就是后面 NL2SQL 的语义检索库：用户问问题时，把问题转向量，在这个索引里面找最相似的商品 / 评价，告诉大模型：“你应该去查这几张、这几条数据”，用来缩小 SQL 的查询范围，是 RAG + NL2SQL 的核心。

# >
# > 注意：这个是轻量方案，没有用 FAISS / Chroma / Milvus，直接 JSON 存向量，适合课程演示、小数据量。

import json
from sqlalchemy import bindparam, text
from math import sqrt  # 计算向量长度时开平方。
from app.database import QuerySessionLocal, query_engine
from app.config import BASE_DIR, settings
from app.services import embedding_service

INDEX_PATH = BASE_DIR / "data" / "semantic_index.json"
BATCH_SIZE = 16  # 每批处理的文本条数
TOP_K = 5  # 每次展示最多五条候选，便于检查相关性。


def rebuild_index() -> int:
    """读取商品和评价的数据，返回索引的记录的数量"""
    if query_engine is None:
        raise ValueError("请先配置数据库只读查询链接")
    # `with QuerySessionLocal()`：拿到只读会话，自动关闭连接；
    with QuerySessionLocal() as db:
        # `products`：查出全部商品：id、名称、类目、描述、价格；
        products = (
            db.execute(
                text(
                    "SELECT id, name, category, description, price from  products ORDER BY id ASC"
                )
            )
            .mappings()
            .all()
        )
        # `reviews`：联表查询评价：评价 id、对应的商品名字、评价正文；
        reviews = (
            db.execute(
                text(
                    "SELECT r.id, p.name, r.content from reviews r join products p on r.product_id = p.id ORDER BY r.id ASC"
                )
            )
            .mappings()  # `.mappings()`：返回字典形式，而不是元组，方便后面按 key 拿值。
            .all()
        )
    documents = []
    for product in products:
        documents.append(
            {
                "kind": "product",
                "id": product["id"],
                "text": f"商品：{product['name']}；类目：{product['category']}；描述：{product['description']}",
            }
        )
    for review in reviews:
        documents.append(
            {
                "kind": "review",
                "id": review["id"],
                "text": f"商品：{review['name']}；评价{review['content']}",
            }
        )
    # 如果库里一条商品、一条评论都没有，直接抛出异常，不生成空索引。
    if not documents:
        raise ValueError("没有可建立索引的商品或评论")
    # 分批循环：
    # 1. 每次切最多 16 条；
    # 2. 提取里面的 `text` 数组，调用 `embed_texts`，批量拿到向量；
    # 3. `zip`：把原始文档 和 返回出来的向量一一配对；
    # 4. 装进 `records`：每一条保存：类型、数据库 id、浮点向量数组
    records = []
    for start in range(0, len(documents), BATCH_SIZE):
        batch_texts = documents[
            start : start + BATCH_SIZE
        ]  # 依次取 [0:16]、[16:32] 等批次。
        # 对一批文本进行向量化处理
        vectors = embedding_service.embed_texts([item["text"] for item in batch_texts])
        for item, vector in zip(batch_texts, vectors):
            records.append({"kind": item["kind"], "id": item["id"], "vector": vector})
    payload = {
        "model": settings.EMBEDDING_MODEL,
        "base_url": settings.EMBEDDING_BASE_URL,
        "records": records,
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)  # 创建父级的data目录
    temporary = INDEX_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(INDEX_PATH)
    return len(records)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """接收2个同维度的向量，返回余弦相似度"""
    # cos(a, b) = (a · b) / (|a| × |b|)
    #      = (Σ aᵢ·bᵢ) / (√(Σ aᵢ²) × √(Σ bᵢ²))
    # 参数的 left / right 是来自同一个向量模型的2个等长的浮点向量列表，返回的值介于 -1 和 1之间，越接近1表示越相近
    if not left or len(left) != len(right):
        raise ValueError("向量维度不一致，请重建索引")
    # 把两个相同位置的向量数进行 两两配对  相乘之后再累加求和  得到点积
    dot = sum(a * b for a, b in zip(left, right))
    left_length = sqrt(sum(value * value for value in left))
    right_length = sqrt(sum(value * value for value in right))
    if left_length == 0 or right_length == 0:
        raise ValueError("向量的长度不能为0")
    return dot / (left_length * right_length)


def search_ids(question: str, kind: str) -> list[dict]:
    """按问题和检索的类型，返回相似度降序排序最高的候选ID和分数"""
    # [{"id": 1, "score": 0.81}, {"id": 3, "score": 0.71}]
    if kind not in {"product", "review"}:
        raise ValueError("检索类型只支持商品和评价")
    question = question.strip()
    if not question:
        raise ValueError("检索问题不能为空")
    if not INDEX_PATH.exists():
        raise ValueError("索引文件不存在，请先执行索引重建操作")
    payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if (
        payload["model"] != settings.EMBEDDING_MODEL
        or payload["base_url"] != settings.EMBEDDING_BASE_URL
    ):
        raise ValueError("向量模型ID或服务地址已变更，请重建索引")
    candidates = [item for item in payload["records"] if item["kind"] == kind]
    if not candidates:
        return []
    vector = embedding_service.embed_texts([question])[0]
    hits = []
    for item in candidates:
        hits.append(
            {"id": item["id"], "score": cosine_similarity(vector, item["vector"])}
        )
    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[:TOP_K]


# 两条回查 SQL 固定不变，用 :ids 占位符接收候选 ID 列表；占位符由 SQLAlchemy 绑定，不做字符串拼接。
DETAIL_SQL = {
    # 商品：名称、类目、描述与价格。
    "product": "SELECT id, name, category, description, price FROM products WHERE id IN :ids",
    # 评价：带上所属商品名，便于阅读原文时判断评价对象。
    "review": (
        "SELECT r.id, r.product_id, p.name AS product_name, r.rating, r.content "
        "FROM reviews AS r JOIN products AS p ON p.id = r.product_id WHERE r.id IN :ids"
    ),
}


def search_records(question: str, kind: str) -> list[dict]:
    """检索候选 ID，回查原始记录，按相似度顺序返回展示数据。"""
    # 未配置只读连接时无法回查原文，先提示配置，避免继续检索。
    if query_engine is None:
        raise ValueError("请先配置 QUERY_DATABASE_URL")
    hits = search_ids(question, kind)
    if not hits:
        return []  # 没有候选就不必连接数据库。
    # expanding=True 让 IN 按列表长度生成对应个数的占位符，列表内容以参数方式绑定。
    statement = text(DETAIL_SQL[kind]).bindparams(bindparam("ids", expanding=True))
    with QuerySessionLocal() as db:
        # db.execute 的第二个参数提供占位符的值，即候选 ID 列表。
        result = db.execute(statement, {"ids": [item["id"] for item in hits]})
        # 转成 {id: 整行字典}，便于下面按 hits 的顺序取用。
        records = {row["id"]: dict(row) for row in result.mappings().all()}
    rows = []
    # IN 不保证返回顺序，按 hits 的排序逐条取回记录。
    for hit in hits:
        row = records.get(hit["id"])
        if row is not None:  # 记录可能已被删除，库中查不到就跳过。
            rows.append(
                {"id": row["id"], "similarity": round(hit["score"], 4), **row}
            )  # 展示保留四位小数，排序用原分数。
    return rows
