"""
FAISS向量索引服务
合同文本向量化、相似案例检索
支持降级到内存索引（无FAISS时）
"""

import json
import logging
import hashlib
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# 尝试导入FAISS
try:
    import faiss
    import numpy as np
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False
    logger.info("FAISS not available, using in-memory fallback")

# 尝试导入sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    logger.info("sentence-transformers not available, using hash-based vectors")


class VectorIndex:
    """向量索引管理器"""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.index = None
        self.metadata = []  # 存储每条向量的元数据
        self._model = None
        self._init_index()

    def _init_index(self):
        """初始化索引"""
        if HAS_FAISS:
            self.index = faiss.IndexFlatIP(self.dimension)  # 内积相似度
        else:
            self.index = []  # 降级为列表存储

    def _get_model(self):
        """获取embedding模型"""
        if self._model is None and HAS_TRANSFORMERS:
            try:
                self._model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            except Exception as e:
                logger.warning(f"Failed to load SentenceTransformer: {e}")
        return self._model

    def _text_to_vector(self, text: str) -> Optional[List[float]]:
        """文本转向量"""
        model = self._get_model()
        if model:
            try:
                vec = model.encode(text[:512])  # 截断长文本
                return vec.tolist()
            except Exception as e:
                logger.warning(f"Encoding error: {e}")

        # 降级：使用hash生成伪向量
        return self._hash_to_vector(text)

    def _hash_to_vector(self, text: str) -> List[float]:
        """使用hash生成伪向量（降级方案）"""
        h = hashlib.md5(text.encode()).hexdigest()
        # 将hex转换为浮点数向量
        vec = []
        for i in range(0, min(len(h), self.dimension * 2), 2):
            val = int(h[i:i+2], 16) / 255.0
            vec.append(val)

        # 填充到目标维度
        while len(vec) < self.dimension:
            vec.append(0.0)

        return vec[:self.dimension]

    def add(self, text: str, metadata: dict) -> int:
        """添加文档到索引"""
        vec = self._text_to_vector(text)
        if vec is None:
            return -1

        idx = len(self.metadata)
        self.metadata.append({
            "text": text[:1000],  # 存储截断文本
            "metadata": metadata,
        })

        if HAS_FAISS:
            import numpy as np
            vec_array = np.array([vec], dtype=np.float32)
            self.index.add(vec_array)
        else:
            self.index.append(vec)

        return idx

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """相似度搜索"""
        vec = self._text_to_vector(query)
        if vec is None or len(self.metadata) == 0:
            return []

        if HAS_FAISS:
            import numpy as np
            query_vec = np.array([vec], dtype=np.float32)
            scores, indices = self.index.search(query_vec, min(top_k, len(self.metadata)))

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and idx < len(self.metadata):
                    results.append({
                        "score": float(score),
                        "text": self.metadata[idx]["text"],
                        "metadata": self.metadata[idx]["metadata"],
                    })
            return results
        else:
            # 降级：计算余弦相似度
            results = []
            for i, stored_vec in enumerate(self.index):
                sim = self._cosine_similarity(vec, stored_vec)
                results.append({
                    "score": sim,
                    "text": self.metadata[i]["text"],
                    "metadata": self.metadata[i]["metadata"],
                })

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def save(self, path: str):
        """保存索引到文件"""
        if HAS_FAISS:
            faiss.write_index(self.index, path)
        import json
        with open(path + ".meta", "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False)

    def load(self, path: str):
        """从文件加载索引"""
        if HAS_FAISS:
            try:
                self.index = faiss.read_index(path)
            except Exception:
                pass
        import json
        try:
            with open(path + ".meta", "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
        except FileNotFoundError:
            pass

    @property
    def size(self) -> int:
        return len(self.metadata)


# 全局索引实例
_global_index: Optional[VectorIndex] = None


def get_vector_index() -> VectorIndex:
    """获取全局向量索引"""
    global _global_index
    if _global_index is None:
        _global_index = VectorIndex()
    return _global_index


async def index_contract(contract_id: int, text: str, metadata: dict = None):
    """索引合同文本"""
    index = get_vector_index()
    meta = {"contract_id": contract_id, "type": "contract", **(metadata or {})}
    index.add(text, meta)
    logger.info(f"Indexed contract {contract_id}, total: {index.size}")


async def search_similar_contracts(query: str, top_k: int = 5) -> List[Dict]:
    """搜索相似合同"""
    index = get_vector_index()
    results = index.search(query, top_k)
    return [r for r in results if r["metadata"].get("type") == "contract"]


async def search_similar_findings(query: str, top_k: int = 5) -> List[Dict]:
    """搜索相似审查发现"""
    index = get_vector_index()
    results = index.search(query, top_k)
    return [r for r in results if r["metadata"].get("type") == "finding"]
