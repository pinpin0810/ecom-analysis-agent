# `embedding_service.py`：**文本向量化服务**
# 作用：接收一批文本，调用兼容 OpenAI 协议的 Embedding（向量嵌入）模型，把每一段文字转换成一串浮点数向量；产出的向量供给后面「语义检索、相似度匹配、RAG、NL2SQL 找相关表」使用。

# >
# > 不一定只能用 OpenAI，像 Ollama、硅基流动、智谱等只要兼容 OpenAI 向量接口都可以接入。
## ✨ 这个代码的亮点

# 1. **批量请求**：减少网络开销；
# 2. **顺序保护**：依靠 index 重排，避开很多人踩的顺序错乱大坑；
# 3. **多层防御校验**：输入、配置、返回索引、向量维度层层拦截脏数据；
# 4. **通用兼容**：只要接口兼容 OpenAI embedding 协议就可以切换模型；
# 5. **提前报错**：异常都主动抛出，不会默默返回错误向量污染后续检索逻辑。

# ## 📌 在项目里的用途

# 后面 `semantic_service.py`（语义检索）会调用它：
# 把用户问题、数据表 / 字段注释全部转为向量，再计算相似度，找到和用户问题相关的数据库表，交给 NL2SQL 模块生成 SQL。

import logging
from openai import OpenAI
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """接收文本列表，返回同顺序的对应的向量列表。批量传入是为了减少请求次数。单个文本传入取第一个"""
    """  ["商品1", "商品2"] -> [[0.12, -0.08, ...]， [0.38, -0.18, ...]]"""
    # 输入合法性校验
    if not texts or any(not value.strip() for value in texts):
        raise ValueError("向量输入文本不能为空")
    # 校验向量服务配置
    if not all(
        (
            settings.EMBEDDING_BASE_URL,
            settings.EMBEDDING_API_KEY,
            settings.EMBEDDING_MODEL,
        )
    ):
        raise ValueError("请配置向量模型的BaseURL、Model和APIKey")
    if settings.EMBEDDING_TIMEOUT_SECONDS <= 0:
        raise ValueError("向量请求的超时时间必须大于 0")
    # 创建客户端、调用向量接口
    with OpenAI(
        base_url=settings.EMBEDDING_BASE_URL,
        api_key=settings.EMBEDDING_API_KEY,
        timeout=settings.EMBEDDING_TIMEOUT_SECONDS,
        max_retries=0,
    ) as client:
        response = client.embeddings.create(
            model=settings.EMBEDDING_MODEL, input=texts, encoding_format="float"
        )  # 要求返回浮点数列表
    # 按响应标注的输入位置恢复顺序，不依赖 data 列表的排列顺序。
    items = sorted(response.data, key=lambda item: item.index)
    # 位置必须完整且不重复；漏回、多回或重复位置都不能继续绑定文档。
    if [item.index for item in items] != list(range(len(texts))):
        raise ValueError("向量服务返回的数量或者位置不正确")
    vectors = [item.embedding for item in items]
    # 同一个模型的向量长度是一样的  维度是固定的
    if not vectors[0] or any(len(v) != len(vectors[0]) for v in vectors):
        raise ValueError("向量服务返回的向量维度不一致")
    logger.info("文本转向量的vectors的长度是 %d", len(vectors))
    return vectors
