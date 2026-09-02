-- pgvector 扩展 (Agent RAG 向量检索)
CREATE EXTENSION IF NOT EXISTS vector;

-- clause_embeddings: 条款向量库 (RAG 数据飞轮)
-- 由 build_rag_corpus.py 写入语料, agent.py 人工修正自动向量化写回
CREATE TABLE IF NOT EXISTS clause_embeddings (
    id BIGSERIAL PRIMARY KEY,
    source_type VARCHAR(32) NOT NULL,           -- review_opinion/template/correction/regulation
    source_id BIGINT,
    contract_type VARCHAR(64),
    clause_type VARCHAR(64),
    risk_level VARCHAR(32),
    clause_text TEXT,
    suggestion_text TEXT,
    legal_basis TEXT,
    embedding vector(512),                      -- bge-small-zh-v1.5 维度
    model_name VARCHAR(128),
    use_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (source_type, source_id)
);

-- HNSW 余弦相似度索引 (加速相似条款检索)
CREATE INDEX IF NOT EXISTS idx_clause_embeddings_vec
    ON clause_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_clause_embeddings_source
    ON clause_embeddings (source_type);
