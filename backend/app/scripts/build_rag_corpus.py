"""
条款 RAG 数据导入脚本
- 读取 review_opinions (52条) + contract_knowledge (8条)
- 调用 embedding 模型向量化
- 写入 clause_embeddings 表
- 跳过已存在的 (按 source_type+source_id 去重)

用法:
    cd /opt/contract-review-system/backend
    source venv/bin/activate
    python -m app.scripts.build_rag_corpus
"""
import sys
import logging
import time
from typing import List, Dict, Any

import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from app.services.contract_rag import EmbeddingService, DB_DSN

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_review_opinions(conn) -> List[Dict[str, Any]]:
    """拉取 review_opinions 全部数据"""
    sql = """
        SELECT
            ro.id, ro.clause_reference, ro.content, ro.suggestion,
            ro.legal_basis, ro.risk_level, ro.opinion_type,
            c.contract_type
        FROM review_opinions ro
        JOIN review_tasks rt ON rt.id = ro.review_task_id
        JOIN contracts c ON c.id = rt.contract_id
        ORDER BY ro.id
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def fetch_contract_knowledge(conn) -> List[Dict[str, Any]]:
    """拉取 contract_knowledge 全部数据"""
    sql = """
        SELECT
            id, contract_type, knowledge_type, title, content
        FROM contract_knowledge
        ORDER BY id
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def fetch_existing_source_ids(conn, source_type: str) -> set:
    """查已入库的 source_id (用于跳过)"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT source_id FROM clause_embeddings WHERE source_type = %s AND source_id IS NOT NULL",
            (source_type,)
        )
        return {row[0] for row in cur.fetchall()}


def build_review_text(row: Dict) -> str:
    """
    构造 embedding 用的文本
    - 优先用 clause_reference (条款名) + content (审查发现)
    - 评审意见的"问题描述"是检索 key
    """
    parts = []
    if row.get("clause_reference"):
        parts.append(f"【{row['clause_reference']}】")
    if row.get("content"):
        parts.append(row["content"])
    return " ".join(parts).strip()


def insert_embedding(
    conn,
    source_type: str,
    source_id: int,
    contract_type: str,
    clause_type: str,
    risk_level: str,
    clause_text: str,
    suggestion_text: str,
    legal_basis: str,
    embedding: List[float],
    model_name: str,
):
    """插入一条 embedding"""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO clause_embeddings (
                source_type, source_id, contract_type, clause_type, risk_level,
                clause_text, suggestion_text, legal_basis, embedding, model_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                source_type, source_id, contract_type, clause_type, risk_level,
                clause_text, suggestion_text, legal_basis, embedding, model_name,
            ),
        )


def build_review_opinions_corpus(conn, emb_service: EmbeddingService) -> int:
    """向量化 review_opinions 入库"""
    rows = fetch_review_opinions(conn)
    if not rows:
        logger.warning("review_opinions 无数据")
        return 0

    existing_ids = fetch_existing_source_ids(conn, "review_opinion")
    logger.info(f"review_opinions: 总 {len(rows)} 条, 已入库 {len(existing_ids)} 条")

    new_rows = [r for r in rows if r["id"] not in existing_ids]
    if not new_rows:
        logger.info("review_opinions 全部已入库, 跳过")
        return 0

    logger.info(f"开始向量化 {len(new_rows)} 条 review_opinions ...")
    texts = [build_review_text(r) for r in new_rows]
    t0 = time.time()
    embeddings = emb_service.embed(texts)
    logger.info(f"embedding 完成, 耗时 {time.time() - t0:.1f}s, shape {embeddings.shape}")

    count = 0
    for row, emb in zip(new_rows, embeddings):
        insert_embedding(
            conn,
            source_type="review_opinion",
            source_id=row["id"],
            contract_type=row.get("contract_type"),
            clause_type=row.get("opinion_type") or row.get("clause_reference"),
            risk_level=row.get("risk_level"),
            clause_text=build_review_text(row),
            suggestion_text=row.get("suggestion") or "",
            legal_basis=row.get("legal_basis") or "",
            embedding=emb.tolist(),
            model_name=emb_service._load_model().get_sentence_embedding_dimension()
                       and "BAAI/bge-small-zh-v1.5" or "unknown",
        )
        count += 1

    conn.commit()
    logger.info(f"✅ review_opinions 入库 {count} 条")
    return count


def build_knowledge_corpus(conn, emb_service: EmbeddingService) -> int:
    """向量化 contract_knowledge 入库"""
    rows = fetch_contract_knowledge(conn)
    if not rows:
        logger.warning("contract_knowledge 无数据")
        return 0

    existing_ids = fetch_existing_source_ids(conn, "knowledge")
    logger.info(f"contract_knowledge: 总 {len(rows)} 条, 已入库 {len(existing_ids)} 条")

    new_rows = [r for r in rows if r["id"] not in existing_ids]
    if not new_rows:
        logger.info("contract_knowledge 全部已入库, 跳过")
        return 0

    logger.info(f"开始向量化 {len(new_rows)} 条 knowledge ...")
    texts = [f"【{r['title']}】 {r['content']}" for r in new_rows]
    t0 = time.time()
    embeddings = emb_service.embed(texts)
    logger.info(f"embedding 完成, 耗时 {time.time() - t0:.1f}s")

    count = 0
    for row, emb in zip(new_rows, embeddings):
        insert_embedding(
            conn,
            source_type="knowledge",
            source_id=row["id"],
            contract_type=row.get("contract_type"),
            clause_type=row.get("knowledge_type"),
            risk_level=None,
            clause_text=f"【{row['title']}】 {row['content'][:500]}",
            suggestion_text=None,
            legal_basis=None,
            embedding=emb.tolist(),
            model_name="BAAI/bge-small-zh-v1.5",
        )
        count += 1

    conn.commit()
    logger.info(f"✅ knowledge 入库 {count} 条")
    return count


def main():
    logger.info("🚀 启动 RAG corpus 构建")
    conn = psycopg2.connect(DB_DSN)
    register_vector(conn)

    emb_service = EmbeddingService()

    n1 = build_review_opinions_corpus(conn, emb_service)
    n2 = build_knowledge_corpus(conn, emb_service)

    # 统计
    with conn.cursor() as cur:
        cur.execute("SELECT source_type, COUNT(*) FROM clause_embeddings GROUP BY source_type")
        stats = cur.fetchall()
        logger.info(f"📊 入库统计: {dict(stats)}")

    conn.close()
    logger.info(f"🎉 完成: review_opinions={n1}, knowledge={n2}")


if __name__ == "__main__":
    main()
