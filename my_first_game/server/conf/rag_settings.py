"""
RAG系统配置文件示例 - Weaviate版本

将这些设置复制到你的 settings.py 文件中来自定义RAG系统行为
"""

# ==================== RAG系统配置 ====================

# 智谱AI嵌入模型设置
RAG_EMBEDDING_MODEL = "embedding-3"        # 智谱AI的嵌入模型
RAG_EMBEDDING_DIMENSIONS = 1024            # 向量维度
RAG_API_KEY = "8725cd11e5cc4c56aabc5142442e59f6.IceSidZVpsp39Mj3"  # 智谱AI API密钥，或设置环境变量 ZHIPUAI_API_KEY

# Weaviate服务器设置
RAG_WEAVIATE_HOST = "localhost"            # Weaviate服务器地址
RAG_WEAVIATE_PORT = 8080                   # Weaviate REST端口
RAG_WEAVIATE_GRPC_PORT = 50051            # Weaviate gRPC端口（可选）

# 文档存储路径
RAG_DOCUMENTS_PATH = "./rag_data/documents"

# 检索设置
RAG_MAX_RESULTS = 5                        # 最多返回的检索结果数
RAG_SIMILARITY_THRESHOLD = 0.7             # 相似度阈值（0-1），越高越严格

# 集合设置
RAG_COLLECTION_NAME = "BattleKnowledge"    # Weaviate collection名称（首字母大写）

# 自动化设置
RAG_AUTO_INDEX = True                      # 系统启动时自动索引文档

# 文档分块设置
RAG_CHUNK_SIZE = 512                       # 每个文档块的最大字符数
RAG_CHUNK_OVERLAP = 64                     # 文档块之间的重叠字符数

# ==================== 高级配置 ====================

# ChromaDB设置
RAG_CHROMA_SETTINGS = {
    "anonymized_telemetry": False,
    "is_persistent": True,
}

# 嵌入模型加载设置
RAG_MODEL_CACHE_FOLDER = "./models"  # 模型缓存目录

# 检索增强设置
RAG_CONTEXT_WINDOW_SIZE = 1000  # 传递给LLM的上下文最大字符数
RAG_ENABLE_RERANKING = False    # 是否启用重排序（需要额外依赖）

# ==================== 开发/调试设置 ====================

# 日志设置
RAG_DEBUG = True               # 启用RAG调试日志
RAG_VERBOSE_LOGGING = False    # 详细日志（包括向量和嵌入信息）

# 性能设置
RAG_BATCH_SIZE = 32           # 批处理大小
RAG_MAX_CACHE_SIZE = 100      # 最大缓存查询数

# ==================== 使用说明 ====================

"""
1. 安装依赖：
   pip install weaviate-client langchain-community

2. 启动Weaviate服务（使用Docker）：
   docker run -p 8080:8080 -p 50051:50051 \
     --env AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
     --env PERSISTENCE_DATA_PATH=/var/lib/weaviate \
     --env DEFAULT_VECTORIZER_MODULE=none \
     --env CLUSTER_HOSTNAME=node1 \
     semitechnologies/weaviate:latest

3. 获取智谱AI API密钥：
   - 访问 https://open.bigmodel.cn/
   - 注册账号并获取API密钥
   - 在配置中设置 RAG_API_KEY 或设置环境变量 ZHIPUAI_API_KEY

4. 将需要的配置复制到 my_first_game/server/conf/settings.py

5. 重启Evennia服务器

6. 游戏内使用命令：
   - rag status          查看系统状态
   - rag add <知识>      添加战斗知识
   - rag reindex         重新索引文档

7. 文档管理：
   - 在 ./rag_data/documents/ 目录下放置 .txt 或 .md 文件
   - 系统会自动索引这些文件
   - 支持中文内容

8. 效果验证：
   - 开始战斗时，系统会自动检索相关知识
   - LLM会基于检索到的上下文生成更丰富的叙述

9. 故障排除：
   - 如果连接失败，检查Weaviate是否正在运行
   - 如果embedding失败，检查智谱AI API密钥是否正确
   - 查看Evennia日志获取详细错误信息
""" 