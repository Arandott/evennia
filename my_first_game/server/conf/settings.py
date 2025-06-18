r"""
Evennia settings file.

The available options are found in the default settings file found
here:

https://www.evennia.com/docs/latest/Setup/Settings-Default.html

Remember:

Don't copy more from the default file than you actually intend to
change; this will make sure that you don't overload upstream updates
unnecessarily.

When changing a setting requiring a file system path (like
path/to/actual/file.py), use GAME_DIR and EVENNIA_DIR to reference
your game folder and the Evennia library folders respectively. Python
paths (path.to.module) should be given relative to the game's root
folder (typeclasses.foo) whereas paths within the Evennia library
needs to be given explicitly (evennia.foo).

If you want to share your game dir, including its settings, you can
put secret game- or server-specific settings in secret_settings.py.

"""

# Use the defaults from Evennia unless explicitly overridden
from evennia.settings_default import *

######################################################################
# Evennia base server config
######################################################################

# This is the name of your game. Make it catchy!
SERVERNAME = "my_first_game"

# LLM_HOST = "https://api.deepseek.com"
# LLM_PATH = "/v1/chat/completions"
# LLM_HEADERS = {"Content-Type": ["application/json"],
#                "Authorization": ["Bearer sk-5ffa791814f145979a06db7e63ce603d"]}
# LLM_PROMPT_KEYNAME = "messages"
# LLM_REQUEST_BODY = {
#                         "model": "deepseek-chat",
#                         "temperature": 0.7,
#                         "max_tokens": 128,
#                    }\
    
LLM_API_TYPE = "openai"
LLM_API_KEY = "sk-5ffa791814f145979a06db7e63ce603d"  # 替换为实际的 API 密钥
LLM_MODEL = "deepseek-chat"
LLM_HOST = "https://api.deepseek.com"
LLM_PATH = "/v1/chat/completions"
LLM_HEADERS = {"Content-Type": ["application/json"]}
LLM_REQUEST_BODY = {
    "model": "deepseek-chat",
    "temperature": 0.9,
    "max_tokens": 256,
}


# 可选：添加 batchcode 路径以支持构建脚本
BASE_BATCHPROCESS_PATHS += ["evennia.contrib.tutorials.evadventure.batchscripts"]

LOG_LEVEL = "DEBUG"

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
RAG_SIMILARITY_THRESHOLD = 0.5             # 相似度阈值（0-1），越高越严格

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



######################################################################
# Settings given in secret_settings.py override those in this file.
######################################################################
try:
    from server.conf.secret_settings import *
except ImportError:
    print("secret_settings.py file not found or failed to import.")
