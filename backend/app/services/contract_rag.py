"""
条款级 RAG 检索服务
- 数据源: review_opinions (已审合同的修改经验) + contract_knowledge (法律知识)
- 检索: 条款文本 → top-K 类似的已审案例 (向量余弦相似度)
- 缓存: Redis (按 hash(clause_type+text) 索引)
"""
import os
import json
import hashlib
import logging
import asyncio
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict, field

import numpy as np
import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

logger = logging.getLogger(__name__)

# ============== 配置 ==============

DB_DSN = os.getenv(
    "DATABASE_URL",
    "host=127.0.0.1 port=5432 dbname=contract_review user=postgres password=postgres",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

# Embedding 模型 — CPU 友好, 512 维
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
EMBEDDING_DIM = 512  # bge-small-zh

# 检索默认
DEFAULT_TOP_K = 3
SIMILARITY_THRESHOLD = 0.55  # 余弦相似度阈值, 低于此不返回

# 缓存
REDIS_CACHE_TTL = 86400  # 24h

# ============== 数据类 ==============

@dataclass
class RetrievedClause:
    """检索到的类似条款"""
    id: int
    source_type: str
    clause_text: str
    suggestion_text: Optional[str] = None
    legal_basis: Optional[str] = None
    contract_type: Optional[str] = None
    clause_type: Optional[str] = None
    risk_level: Optional[str] = None
    similarity: float = 0.0


@dataclass
class RAGContext:
    """注入到 DeepSeek prompt 的 RAG 上下文"""
    retrieved: List[RetrievedClause] = field(default_factory=list)
    formatted_block: str = ""

    def is_empty(self) -> bool:
        return len(self.retrieved) == 0


# ============== Embedding 封装 ==============

class EmbeddingService:
    """Embedding 模型单例 (懒加载, 避免启动慢)"""
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"加载 embedding 模型: {EMBEDDING_MODEL_NAME}")
            self._model = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu")
            test_emb = self._model.encode(["test"], normalize_embeddings=True)
            logger.info(f"模型加载完成, 维度 {test_emb.shape[1]}")
        return self._model

    def embed(self, texts: List[str]) -> np.ndarray:
        model = self._load_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return np.asarray(embeddings, dtype=np.float32)

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0].tolist()


# ============== 缓存封装 ==============

class CacheService:
    """Redis 缓存 (RAG 检索结果)"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._redis = None
        try:
            import redis
            self._redis = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2)
            self._redis.ping()
            logger.info("Redis 缓存已连接")
        except Exception as e:
            logger.warning(f"Redis 不可用, 降级为无缓存: {e}")
            self._redis = None

    @staticmethod
    def _hash_key(clause_type: str, text: str) -> str:
        h = hashlib.md5(f"{clause_type}|{text}".encode("utf-8")).hexdigest()
        return f"rag:{clause_type or 'all'}:{h}"

    def get(self, clause_type: str, text: str) -> Optional[List[Dict]]:
        if not self._redis:
            return None
        try:
            key = self._hash_key(clause_type, text)
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.debug(f"缓存读失败: {e}")
            return None

    def set(self, clause_type: str, text: str, value: List[Dict]) -> None:
        if not self._redis:
            return
        try:
            key = self._hash_key(clause_type, text)
            self._redis.setex(key, REDIS_CACHE_TTL, json.dumps(value, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"缓存写失败: {e}")


# ============== RAG 检索 ==============

class ContractRAG:
    """条款级 RAG 检索器"""

    def __init__(self):
        self.embedding = EmbeddingService()
        self.cache = CacheService()
        self._db_conn = None

    def _get_conn(self):
        if self._db_conn is None or self._db_conn.closed:
            self._db_conn = psycopg2.connect(DB_DSN)
            register_vector(self._db_conn)
        return self._db_conn

    def retrieve(
        self,
        clause_text: str,
        contract_type: Optional[str] = None,
        clause_type: Optional[str] = None,
        top_k: int = DEFAULT_TOP_K,
        use_cache: bool = True,
    ) -> RAGContext:
        """检索类似条款"""
        if use_cache:
            cached = self.cache.get(clause_type or "", clause_text)
            if cached:
                logger.debug(f"RAG 缓存命中: {len(cached)} 条")
                retrieved = [RetrievedClause(**item) for item in cached]
                return RAGContext(
                    retrieved=retrieved,
                    formatted_block=self._format_block(retrieved),
                )

        emb = self.embedding.embed_one(clause_text)

        try:
            conn = self._get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # where 条件 (阈值内联, 避免占位符混乱)
                where_clauses = [f"embedding <=> %s::vector < {1.0 - SIMILARITY_THRESHOLD}"]
                where_params: List[Any] = []
                if contract_type:
                    where_clauses.append(
                        "(contract_type = %s OR contract_type = 'all' OR contract_type IS NULL)"
                    )
                    where_params.append(contract_type)
                if clause_type:
                    where_clauses.append("(clause_type = %s OR clause_type IS NULL)")
                    where_params.append(clause_type)

                sql = f"""
                    SELECT
                        id, source_type, contract_type, clause_type, risk_level,
                        clause_text, suggestion_text, legal_basis,
                        1 - (embedding <=> %s::vector) AS similarity
                    FROM clause_embeddings
                    WHERE {" AND ".join(where_clauses)}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """
                # 参数顺序: WHERE emb, 过滤条件..., SELECT emb, ORDER emb, LIMIT
                all_params = [emb] + where_params + [emb, emb, top_k]
                cur.execute(sql, all_params)
                rows = cur.fetchall()
        except Exception as e:
            logger.error(f"RAG 检索失败: {e}")
            return RAGContext()

        retrieved = [
            RetrievedClause(
                id=row["id"],
                source_type=row["source_type"],
                clause_text=row["clause_text"],
                suggestion_text=row["suggestion_text"],
                legal_basis=row["legal_basis"],
                contract_type=row["contract_type"],
                clause_type=row["clause_type"],
                risk_level=row["risk_level"],
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]

        if use_cache and retrieved:
            try:
                self.cache.set(
                    clause_type or "",
                    clause_text,
                    [asdict(r) for r in retrieved],
                )
            except Exception as e:
                logger.debug(f"缓存写失败: {e}")

        if retrieved:
            try:
                ids = [r.id for r in retrieved]
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE clause_embeddings SET use_count = use_count + 1 WHERE id = ANY(%s)",
                        (ids,),
                    )
                conn.commit()
            except Exception as e:
                logger.debug(f"use_count 更新失败: {e}")

        return RAGContext(
            retrieved=retrieved,
            formatted_block=self._format_block(retrieved),
        )

    @staticmethod
    def _format_block(retrieved: List[RetrievedClause]) -> str:
        if not retrieved:
            return ""

        lines = ["\n## 📚 历史类似条款参考 (来自已审合同, 仅作参考)"]
        for i, r in enumerate(retrieved, 1):
            sim_pct = f"{r.similarity:.0%}"
            risk_tag = f"[{r.risk_level}]" if r.risk_level else ""
            lines.append(f"\n### 参考 {i} {risk_tag} (相似度 {sim_pct})")
            lines.append(f"**类似条款/问题**: {r.clause_text[:200]}")
            if r.suggestion_text:
                lines.append(f"**修改建议**: {r.suggestion_text[:300]}")
            if r.legal_basis:
                lines.append(f"**法律依据**: {r.legal_basis[:200]}")
        return "\n".join(lines)


# ============== 异步入口 ==============

def retrieve_for_clause(
    clause_text: str,
    contract_type: Optional[str] = None,
    clause_type: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K,
) -> RAGContext:
    rag = ContractRAG()
    return rag.retrieve(clause_text, contract_type, clause_type, top_k)


async def retrieve_for_clause_async(
    clause_text: str,
    contract_type: Optional[str] = None,
    clause_type: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K,
) -> RAGContext:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: retrieve_for_clause(clause_text, contract_type, clause_type, top_k),
    )


# ============== 单例 ==============

_rag_singleton: Optional[ContractRAG] = None

def get_rag() -> ContractRAG:
    global _rag_singleton
    if _rag_singleton is None:
        _rag_singleton = ContractRAG()
    return _rag_singleton


# ============== Prompt 注入辅助 ==============

def _format_rag_blocks(rag_contexts):
    """把多个 RAG context 格式化为注入 prompt 的字符串"""
    if not rag_contexts:
        return ""
    lines = ["\n## 📚 历史类似条款参考 (来自已审合同, 仅作参考)"]
    seen = set()
    for ctx in rag_contexts:
        if ctx is None or ctx.is_empty():
            continue
        for r in ctx.retrieved:
            key = (r.clause_text[:50], r.suggestion_text[:30] if r.suggestion_text else "")
            if key in seen:
                continue
            seen.add(key)
            sim_pct = f"{r.similarity:.0%}"
            risk_tag = f"[{r.risk_level}]" if r.risk_level else ""
            lines.append(f"\n### 参考 {risk_tag} (相似度 {sim_pct})")
            lines.append(f"**类似条款/问题**: {r.clause_text[:200]}")
            if r.suggestion_text:
                lines.append(f"**修改建议**: {r.suggestion_text[:300]}")
            if r.legal_basis:
                lines.append(f"**法律依据**: {r.legal_basis[:200]}")
    return "\n".join(lines) if len(seen) > 0 else ""


async def enhance_with_rag(contract, findings):
    """异步入口: 对 findings 做 RAG 检索, 返回 rag_contexts 列表"""
    rag = get_rag()
    contexts = []
    for f in findings:
        clause_text = f.get("content", "") or f.get("clause", "") or ""
        if clause_text:
            ctx = rag.retrieve(clause_text, top_k=2)
            if not ctx.is_empty():
                contexts.append(ctx)
    return contexts
