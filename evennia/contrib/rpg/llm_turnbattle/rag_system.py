"""
RAG (Retrieval-Augmented Generation) 系统 - Weaviate版本
为战斗叙述提供上下文增强的检索功能

依赖：
pip install weaviate-client langchain-community
"""

import json
import os
import hashlib
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

from evennia.utils import logger
from evennia.utils.utils import make_iter
from django.conf import settings

# 延迟导入，避免在没有安装依赖时出错
try:
    import weaviate
    import weaviate.classes.config as wvc
    from weaviate.classes.query import Filter
    from langchain_community.embeddings import ZhipuAIEmbeddings
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    logger.log_warn("RAG系统依赖未安装: pip install weaviate-client langchain-community")
    DEPENDENCIES_AVAILABLE = False


# ==================== 配置 ====================

# 默认设置，可通过Evennia设置覆盖
DEFAULT_RAG_CONFIG = {
    "embedding_model": "embedding-3",  # 智谱AI embedding模型
    "embedding_dimensions": 1024,     # 向量维度
    "api_key": "",                    # 智谱AI API密钥，应在settings中设置
    "weaviate_host": "localhost",     # Weaviate服务器地址
    "weaviate_port": 8080,           # Weaviate REST端口
    "weaviate_grpc_port": 50051,     # Weaviate gRPC端口
    "documents_path": "./rag_data/documents", 
    "max_results": 5,
    "similarity_threshold": 0.5,
    "collection_name": "BattleKnowledge",  # Weaviate collection名称（首字母大写）
    "auto_index": True,  # 自动索引新文档
    "chunk_size": 512,   # 文档分块大小
    "chunk_overlap": 64, # 分块重叠
}

def get_rag_config():
    """获取RAG配置，优先使用Evennia设置"""
    config = DEFAULT_RAG_CONFIG.copy()
    
    # 从Evennia设置中更新配置
    for key in config.keys():
        setting_key = f"RAG_{key.upper()}"
        if hasattr(settings, setting_key):
            config[key] = getattr(settings, setting_key)
    
    return config


# ==================== 数据结构 ====================

@dataclass
class DocumentChunk:
    """文档块数据结构"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentChunk':
        return cls(**data)


@dataclass
class RetrievalResult:
    """检索结果数据结构"""
    chunk: DocumentChunk
    score: float
    relevance: str  # "high", "medium", "low"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk": self.chunk.to_dict(),
            "score": self.score,
            "relevance": self.relevance
        }


# ==================== 嵌入服务 ====================

class EmbeddingService:
    """智谱AI嵌入向量生成服务"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or get_rag_config()
        self._embedder = None
        self._initialized = False
    
    @property
    def embedder(self):
        """懒加载智谱AI嵌入模型"""
        if not DEPENDENCIES_AVAILABLE:
            raise ImportError("RAG依赖未安装")
            
        if not self._initialized:
            try:
                api_key = self.config.get("api_key")
                if not api_key:
                    # 尝试从环境变量获取
                    api_key = os.getenv("ZHIPUAI_API_KEY")
                    
                if not api_key:
                    raise ValueError("未设置智谱AI API密钥，请在配置中设置 api_key 或设置环境变量 ZHIPUAI_API_KEY")
                
                logger.log_info(f"初始化智谱AI嵌入模型: {self.config['embedding_model']}")
                self._embedder = ZhipuAIEmbeddings(
                    model=self.config["embedding_model"],
                    dimensions=self.config["embedding_dimensions"],
                    api_key=api_key
                )
                self._initialized = True
                logger.log_info("智谱AI嵌入模型初始化成功")
            except Exception as e:
                logger.log_err(f"智谱AI嵌入模型初始化失败: {e}")
                raise
        return self._embedder
    
    def encode(self, texts: List[str]) -> List[List[float]]:
        """将文本编码为向量"""
        try:
            # 智谱AI支持批量处理
            embeddings = self.embedder.embed_documents(texts)
            return embeddings
        except Exception as e:
            logger.log_err(f"批量文本编码失败: {e}")
            return []
    
    def encode_single(self, text: str) -> List[float]:
        """编码单个文本"""
        try:
            embedding = self.embedder.embed_query(text)
            return embedding
        except Exception as e:
            logger.log_err(f"单个文本编码失败: {e}")
            return []


# ==================== 向量数据库 ====================

class VectorDatabase:
    """Weaviate向量数据库封装"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or get_rag_config()
        self._client = None
        self._collection = None
        self.embedding_service = EmbeddingService(self.config)
    
    @property
    def client(self):
        """懒加载Weaviate客户端"""
        if not DEPENDENCIES_AVAILABLE:
            raise ImportError("RAG依赖未安装")
            
        if self._client is None:
            try:
                logger.log_info(f"连接到Weaviate: {self.config['weaviate_host']}:{self.config['weaviate_port']}")
                
                # 尝试连接（先尝试带gRPC端口）
                try:
                    self._client = weaviate.connect_to_local(
                        host=self.config["weaviate_host"],
                        port=self.config["weaviate_port"],
                        grpc_port=self.config["weaviate_grpc_port"]
                    )
                except Exception:
                    # 如果gRPC端口连接失败，跳过初始化检查
                    logger.log_info("gRPC端口连接失败，使用跳过初始化检查的方式连接")
                    self._client = weaviate.connect_to_local(
                        host=self.config["weaviate_host"],
                        port=self.config["weaviate_port"],
                        skip_init_checks=True
                    )
                
                # 测试连接
                if self._client.is_ready():
                    logger.log_info("Weaviate客户端连接成功")
                else:
                    raise ConnectionError("Weaviate服务器未就绪")
                    
            except Exception as e:
                logger.log_err(f"Weaviate客户端连接失败: {e}")
                raise
        return self._client
    
    @property
    def collection(self):
        """获取或创建集合"""
        if self._collection is None:
            try:
                collection_name = self.config["collection_name"]
                
                # 检查集合是否存在
                if self.client.collections.exists(collection_name):
                    self._collection = self.client.collections.get(collection_name)
                    logger.log_info(f"使用现有集合: {collection_name}")
                else:
                    # 创建新集合
                    self._collection = self.client.collections.create(
                        name=collection_name,
                        properties=[
                            wvc.Property(name="title", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="content", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="source", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="file_path", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="chunk_index", data_type=wvc.DataType.INT),
                            wvc.Property(name="file_size", data_type=wvc.DataType.INT),
                            wvc.Property(name="last_modified", data_type=wvc.DataType.NUMBER),
                            wvc.Property(name="content_hash", data_type=wvc.DataType.TEXT),
                            wvc.Property(name="chunk_id", data_type=wvc.DataType.TEXT),
                        ],
                        vectorizer_config=wvc.Configure.Vectorizer.none()  # 手动提供向量
                    )
                    logger.log_info(f"创建新集合: {collection_name}")
                    
            except Exception as e:
                logger.log_err(f"集合操作失败: {e}")
                raise
        return self._collection
    
    def add_documents(self, chunks: List[DocumentChunk]) -> bool:
        """添加文档块到Weaviate向量数据库"""
        try:
            if not chunks:
                return True
                
            logger.log_info(f"为{len(chunks)}个文档块生成嵌入向量...")
            
            # 准备内容用于生成向量
            contents = [chunk.content for chunk in chunks]
            
            # 生成嵌入向量
            embeddings = self.embedding_service.encode(contents)
            
            if not embeddings:
                logger.log_err("嵌入向量生成失败")
                return False
            
            # 批量插入到Weaviate
            objects_to_insert = []
            for i, chunk in enumerate(chunks):
                # 计算内容哈希
                content_hash = hashlib.md5(chunk.content.encode()).hexdigest()
                
                # 准备Weaviate对象数据
                properties = {
                    "title": chunk.metadata.get("source", "unknown"),
                    "content": chunk.content,
                    "source": chunk.metadata.get("source", "unknown"),
                    "file_path": chunk.metadata.get("file_path", ""),
                    "chunk_index": chunk.metadata.get("chunk_index", 0),
                    "file_size": chunk.metadata.get("file_size", 0),
                    "last_modified": chunk.metadata.get("last_modified", 0),
                    "content_hash": content_hash,
                    "chunk_id": chunk.id,
                }
                
                # 添加到批量插入列表
                objects_to_insert.append({
                    "properties": properties,
                    "vector": embeddings[i]
                })
            
            # 执行批量插入
            if objects_to_insert:
                with self.collection.batch.dynamic() as batch:
                    for obj in objects_to_insert:
                        batch.add_object(
                            properties=obj["properties"],
                            vector=obj["vector"]
                        )
                
                logger.log_info(f"成功添加{len(chunks)}个文档块到Weaviate")
                return True
            else:
                logger.log_warn("没有有效的文档块可添加")
                return False
            
        except Exception as e:
            logger.log_err(f"添加文档到Weaviate失败: {e}")
            logger.log_err(traceback.format_exc())
            return False
    
    def search(self, query: str, max_results: int = None) -> List[RetrievalResult]:
        """在Weaviate中搜索相关文档"""
        try:
            max_results = max_results or self.config["max_results"]
            
            # 生成查询向量
            query_embedding = self.embedding_service.encode_single(query)
            if not query_embedding:
                logger.log_err("查询向量生成失败")
                return []
            
            # 执行向量搜索
            response = self.collection.query.near_vector(
                near_vector=query_embedding,
                limit=max_results,
                return_metadata=["score"]  # 返回相似度分数
            )
            
            logger.log_info(f"搜索结果: {response}") 
            
            # 处理结果
            retrieval_results = []
            threshold = self.config["similarity_threshold"]
            
            for i, obj in enumerate(response.objects):
                # Weaviate返回的是距离，需要转换为相似度
                # 注意：Weaviate的分数已经是相似度形式（0-1），值越高越相似
                similarity = obj.metadata.score if obj.metadata.score else 0.0
                
                # 从Weaviate对象构建文档块
                metadata = {
                    "source": obj.properties.get("source", "unknown"),
                    "chunk_index": obj.properties.get("chunk_index", 0),
                    "file_size": obj.properties.get("file_size", 0),
                }
                
                chunk = DocumentChunk(
                    id=f"search_result_{i}",
                    content=obj.properties.get("content", ""),
                    metadata=metadata
                )
                
                retrieval_results.append(RetrievalResult(
                    chunk=chunk,
                    score=similarity,
                    relevance="high"
                ))
            
            logger.log_info(f"搜索到{len(retrieval_results)}个相关文档块")
            return retrieval_results
            
        except Exception as e:
            logger.log_err(f"Weaviate向量搜索失败: {e}")
            logger.log_err(traceback.format_exc())
            return []
    
    def get_indexed_documents(self) -> Dict[str, Dict[str, Any]]:
        """获取已索引的文档信息"""
        try:
            # 查询所有文档，按file_path分组
            response = self.collection.query.fetch_objects(
                limit=10000,  # 假设不超过1万个文档块
                return_properties=["file_path", "last_modified", "file_size", "source"]
            )
            
            indexed_docs = {}
            for obj in response.objects:
                file_path = obj.properties.get("file_path", "")
                if file_path and file_path not in indexed_docs:
                    indexed_docs[file_path] = {
                        "last_modified": obj.properties.get("last_modified", 0),
                        "file_size": obj.properties.get("file_size", 0),
                        "source": obj.properties.get("source", "unknown"),
                    }
            
            return indexed_docs
            
        except Exception as e:
            logger.log_err(f"获取已索引文档失败: {e}")
            return {}
    
    def delete_document_by_path(self, file_path: str) -> bool:
        """删除指定文件路径的所有文档块"""
        try:
            # 使用过滤器找到所有匹配的文档
            filter_by_path = Filter.by_property("file_path").equal(file_path)
            
            response = self.collection.query.fetch_objects(
                filters=filter_by_path,
                limit=1000  # 假设单个文件不会超过1000个块
            )
            
            # 删除找到的所有对象
            deleted_count = 0
            for obj in response.objects:
                try:
                    self.collection.data.delete_by_id(obj.uuid)
                    deleted_count += 1
                except Exception as e:
                    logger.log_warn(f"删除对象 {obj.uuid} 失败: {e}")
            
            if deleted_count > 0:
                logger.log_info(f"删除了文件 {file_path} 的 {deleted_count} 个文档块")
                return True
            else:
                logger.log_info(f"文件 {file_path} 没有找到需要删除的文档块")
                return False
                
        except Exception as e:
            logger.log_err(f"删除文档失败 {file_path}: {e}")
            return False
    
    def document_needs_reindex(self, file_path: str, current_mtime: float, current_size: int) -> bool:
        """检查文档是否需要重新索引"""
        try:
            indexed_docs = self.get_indexed_documents()
            
            if file_path not in indexed_docs:
                logger.log_info(f"文档 {file_path} 未被索引，需要添加")
                return True
            
            doc_info = indexed_docs[file_path]
            indexed_mtime = doc_info.get("last_modified", 0)
            indexed_size = doc_info.get("file_size", 0)
            
            # 检查修改时间和文件大小
            if abs(current_mtime - indexed_mtime) > 1:  # 允许1秒的误差
                logger.log_info(f"文档 {file_path} 修改时间变化，需要重新索引")
                return True
                
            if current_size != indexed_size:
                logger.log_info(f"文档 {file_path} 文件大小变化，需要重新索引")
                return True
            
            return False
            
        except Exception as e:
            logger.log_err(f"检查文档索引状态失败 {file_path}: {e}")
            return True  # 出错时保守地重新索引

    def get_stats(self) -> Dict[str, Any]:
        """获取Weaviate数据库统计信息"""
        try:
            # 获取集合中的对象总数
            count = self.collection.aggregate.over_all().total_count
            
            # 获取已索引的文档数量
            indexed_docs = self.get_indexed_documents()
            
            return {
                "total_documents": count,
                "total_files": len(indexed_docs),
                "collection_name": self.config["collection_name"],
                "embedding_model": self.config["embedding_model"],
                "weaviate_host": f"{self.config['weaviate_host']}:{self.config['weaviate_port']}",
                "embedding_dimensions": self.config["embedding_dimensions"]
            }
        except Exception as e:
            logger.log_err(f"获取Weaviate统计信息失败: {e}")
            return {}


# ==================== 文档处理器 ====================

class DocumentProcessor:
    """文档处理器：负责文档的分块和预处理"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or get_rag_config()
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[DocumentChunk]:
        """将文本分块"""
        chunk_size = self.config["chunk_size"]
        chunk_overlap = self.config["chunk_overlap"]
        metadata = metadata or {}
        
        chunks = []
        text = text.strip()
        
        if len(text) <= chunk_size:
            # 文本较短，不需要分块
            chunk_id = self._generate_chunk_id(text, metadata)
            chunks.append(DocumentChunk(
                id=chunk_id,
                content=text,
                metadata=metadata
            ))
        else:
            # 按段落分块
            paragraphs = text.split('\n\n')
            current_chunk = ""
            chunk_index = 0
            
            for paragraph in paragraphs:
                if len(current_chunk) + len(paragraph) <= chunk_size:
                    current_chunk += paragraph + "\n\n"
                else:
                    if current_chunk.strip():
                        chunk_id = self._generate_chunk_id(current_chunk, metadata, chunk_index)
                        chunks.append(DocumentChunk(
                            id=chunk_id,
                            content=current_chunk.strip(),
                            metadata={**metadata, "chunk_index": chunk_index}
                        ))
                        chunk_index += 1
                    
                    current_chunk = paragraph + "\n\n"
            
            # 添加最后一个块
            if current_chunk.strip():
                chunk_id = self._generate_chunk_id(current_chunk, metadata, chunk_index)
                chunks.append(DocumentChunk(
                    id=chunk_id,
                    content=current_chunk.strip(),
                    metadata={**metadata, "chunk_index": chunk_index}
                ))
        
        return chunks
    
    def _generate_chunk_id(self, content: str, metadata: Dict[str, Any], index: int = 0) -> str:
        """生成块ID"""
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        source = metadata.get("source", "unknown")
        return f"{source}_{index}_{content_hash}"
    
    def load_document_from_file(self, file_path: str) -> List[DocumentChunk]:
        """从文件加载文档"""
        try:
            path = Path(file_path)
            if not path.exists():
                logger.log_err(f"文件不存在: {file_path}")
                return []
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metadata = {
                "source": path.name,
                "file_path": str(path),
                "file_size": path.stat().st_size,
                "last_modified": path.stat().st_mtime
            }
            
            return self.chunk_text(content, metadata)
            
        except Exception as e:
            logger.log_err(f"加载文档失败 {file_path}: {e}")
            return []


# ==================== RAG管理器 ====================

class RAGManager:
    """RAG系统主管理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or get_rag_config()
        self.vector_db = VectorDatabase(self.config)
        self.doc_processor = DocumentProcessor(self.config)
        self._knowledge_cache = {}
    
    def initialize(self) -> bool:
        """初始化RAG系统"""
        try:
            if not DEPENDENCIES_AVAILABLE:
                logger.log_warn("RAG系统依赖未安装，将使用后备模式")
                return False
            
            # 确保文档目录存在
            docs_path = Path(self.config["documents_path"])
            docs_path.mkdir(parents=True, exist_ok=True)
            
            # 自动索引文档
            if self.config["auto_index"]:
                self.index_documents()
            
            logger.log_info("RAG系统初始化成功")
            return True
            
        except Exception as e:
            logger.log_err(f"RAG系统初始化失败: {e}")
            logger.log_err(traceback.format_exc())
            return False
    
    def index_documents(self, force_reindex: bool = False) -> int:
        """增量索引文档目录中的文档
        
        Args:
            force_reindex: 是否强制重新索引所有文档
            
        Returns:
            int: 新增或更新的文档块数量
        """
        try:
            docs_path = Path(self.config["documents_path"])
            if not docs_path.exists():
                logger.log_info(f"文档目录不存在，创建: {docs_path}")
                docs_path.mkdir(parents=True, exist_ok=True)
                self._create_sample_documents(docs_path)
                return 0
            
            # 扫描文档文件
            doc_files = list(docs_path.glob("*.txt")) + list(docs_path.glob("*.md"))
            if not doc_files:
                logger.log_info("未找到文档文件，创建示例文档")
                self._create_sample_documents(docs_path)
                doc_files = list(docs_path.glob("*.txt"))
            
            # 获取已索引的文档信息
            indexed_docs = self.vector_db.get_indexed_documents()
            
            # 找出当前存在的文件路径
            current_file_paths = set(str(doc_file.resolve()) for doc_file in doc_files)
            indexed_file_paths = set(indexed_docs.keys())
            
            # 清理已删除文件的索引
            deleted_files = indexed_file_paths - current_file_paths
            for deleted_file in deleted_files:
                logger.log_info(f"清理已删除文件的索引: {deleted_file}")
                self.vector_db.delete_document_by_path(deleted_file)
            
            # 处理需要索引的文档
            all_chunks = []
            processed_count = 0
            
            for doc_file in doc_files:
                file_path = str(doc_file.resolve())
                file_stat = doc_file.stat()
                current_mtime = file_stat.st_mtime
                current_size = file_stat.st_size
                
                # 检查是否需要重新索引
                needs_reindex = force_reindex or self.vector_db.document_needs_reindex(
                    file_path, current_mtime, current_size
                )
                
                if needs_reindex:
                    logger.log_info(f"{'强制重新索引' if force_reindex else '增量索引'}: {doc_file.name}")
                    
                    # 如果文档已存在，先删除旧的索引
                    if file_path in indexed_docs and not force_reindex:
                        logger.log_info(f"删除文档的旧索引: {doc_file.name}")
                        self.vector_db.delete_document_by_path(file_path)
                    
                    # 加载并处理文档
                    chunks = self.doc_processor.load_document_from_file(str(doc_file))
                    if chunks:
                        all_chunks.extend(chunks)
                        processed_count += len(chunks)
                        logger.log_info(f"处理文档 {doc_file.name}: {len(chunks)} 个块")
                else:
                    logger.log_info(f"跳过未修改的文档: {doc_file.name}")
            
            # 批量添加新的文档块到向量数据库
            if all_chunks:
                success = self.vector_db.add_documents(all_chunks)
                if success:
                    logger.log_info(f"增量索引完成，共处理 {processed_count} 个文档块")
                    return processed_count
                else:
                    logger.log_err("向量数据库添加文档失败")
                    return 0
            else:
                logger.log_info("没有需要索引的新文档或修改的文档")
                return 0
            
        except Exception as e:
            logger.log_err(f"增量文档索引失败: {e}")
            logger.log_err(traceback.format_exc())
            return 0
    
    def _create_sample_documents(self, docs_path: Path):
        """创建示例文档"""
        sample_docs = {
            "武侠招式.txt": """
【剑法招式】
- 一剑封喉：迅疾如电的致命一击，专攻要害
- 剑气纵横：以内力催动剑气，远程攻击
- 回风落雁：剑招如风，连绵不绝
- 天外飞仙：剑法的至高境界，飘逸超然

【刀法招式】  
- 霸王举鼎：力大无穷的劈砍
- 柳絮刀法：轻灵如柳絮飞舞
- 断魂刀：专破敌人兵器
- 狂风刀法：如狂风扫叶般猛烈

【掌法招式】
- 降龙十八掌：刚猛无比的掌法
- 如来神掌：佛门至高掌法
- 凌空掌：内力外放的远程攻击
- 寒冰掌：带有寒气的特殊掌法
            """,
            
            "战斗描述.txt": """
【攻击效果描述】
- 命中要害：招式精准击中敌人弱点
- 力量爆发：全力一击展现强大威力
- 技巧精妙：以技巧克服力量不足
- 气势如虹：气势压制对手

【防御反应】
- 惊险躲闪：千钧一发之际的闪避
- 硬抗攻击：以强悍体魄承受伤害
- 巧妙化解：四两拨千斤的化解技巧
- 反击机会：防守中寻找反击时机

【环境描述】
- 尘土飞扬：激烈战斗掀起尘土
- 劲风呼啸：招式带动的气流
- 火花四溅：兵器碰撞的火花
- 地动山摇：强大力量的震撼
            """,
            
            "角色特征.txt": """
【剑客特征】
- 身法飘逸，如风中柳絮
- 剑光闪烁，寒光逼人
- 气质超然，有仙风道骨
- 出手果断，招招致命

【刀客特征】
- 体格雄健，力大无穷
- 刀法凶猛，势如劈山
- 气势豪迈，有万夫不当之勇
- 招式大开大合，威力惊人

【法师特征】
- 身着法袍，手持法杖
- 法术绚烂，光芒四射
- 咒语低吟，神秘莫测
- 元素之力，变化万千

【网球选手特征】
- 身姿矫健，反应敏捷
- 挥拍有力，球技精湛
- 专注投入，永不言败
- 战术灵活，应变自如
            """
        }
        
        for filename, content in sample_docs.items():
            file_path = docs_path / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.log_info(f"创建示例文档: {filename}")
    
    def retrieve_context(self, query: str, context_type: str = "battle") -> List[RetrievalResult]:
        """检索相关上下文"""
        try:
            if not DEPENDENCIES_AVAILABLE:
                return []
            
            # 构建查询
            enhanced_query = f"{context_type} {query}"
            
            # 执行检索
            results = self.vector_db.search(enhanced_query)
            
            # 缓存结果（可选）
            cache_key = hashlib.md5(enhanced_query.encode()).hexdigest()
            self._knowledge_cache[cache_key] = results
            
            return results
            
        except Exception as e:
            logger.log_err(f"上下文检索失败: {e}")
            return []
    
    def get_battle_context(self, attacker, defender, weapon_types: List[str] = None) -> str:
        """获取战斗相关的上下文信息"""
        try:
            # 构建查询词
            query_parts = []
            
            # 角色类型
            if attacker.db.desc:
                query_parts.append(attacker.db.desc or "")
            if defender.db.desc:
                query_parts.append(defender.db.desc or "")
            
            # 武器类型
            if weapon_types:
                query_parts.extend(weapon_types)
            
            # 通用战斗词汇
            query_parts.extend(["战斗", "攻击", "招式", "武器"])
            
            query = " ".join(filter(None, query_parts))
            logger.log_info(f"构建的查询词: {query}")   
            
            # 检索相关信息
            results = self.retrieve_context(query, "battle")
            
            if not results:
                return ""
            
            # 组织上下文
            context_parts = []
            for result in results[:3]:  # 只取前3个最相关的
                content = result.chunk.content.strip()
                if len(content) > 200:
                    content = content[:200] + "..."
                context_parts.append(f"- {content}")
            
            return "\n".join(context_parts) if context_parts else ""
            
        except Exception as e:
            logger.log_err(f"获取战斗上下文失败: {e}")
            return ""
    
    def get_character_context(self, character, weapon_info: Dict[str, Any] = None, role: str = "角色") -> str:
        """为单个角色获取相关的上下文信息
        
        Args:
            character: 角色对象
            weapon_info: 武器信息字典
            role: 角色类型（用于日志）
            
        Returns:
            str: 检索到的上下文文本
        """
        try:
            # 构建查询词
            query_parts = []
            
            # 角色描述
            if hasattr(character, 'db') and character.db.desc:
                desc = character.db.desc.strip()
                if desc:
                    query_parts.append(desc)
                    logger.log_info(f"{role}描述: {desc}")
            
            # 武器信息
            if weapon_info:
                # 武器名称
                weapon_name = weapon_info.get('name', '')
                if weapon_name and weapon_name != "赤手空拳":
                    query_parts.append(weapon_name)
                
                # 武器类型
                weapon_type_name = weapon_info.get('type_name', '')
                if weapon_type_name:
                    query_parts.append(weapon_type_name)
                
                # 武器描述
                weapon_desc = weapon_info.get('desc', '')
                if weapon_desc:
                    query_parts.append(weapon_desc)
                
                logger.log_info(f"{role}武器信息用于检索: {weapon_info}")
            
            # 添加通用战斗词汇
            query_parts.extend(["战斗", "攻击", "招式"])
            
            if not query_parts:
                logger.log_warn(f"{role}没有可用于检索的信息")
                return ""
            
            query = " ".join(filter(None, query_parts))
            logger.log_info(f"{role}检索查询词: {query}")
            
            # 检索相关信息
            results = self.retrieve_context(query, "character")
            
            if not results:
                logger.log_info(f"{role}未检索到相关上下文")
                return ""
            
            # 组织上下文
            context_parts = []
            for i, result in enumerate(results[:2]):  # 每个角色只取前2个最相关的
                content = result.chunk.content.strip()
                if len(content) > 500:  # 稍微短一些，避免prompt过长
                    content = content[:500] + "..."
                context_parts.append(content)
                logger.log_info(f"{role}上下文{i+1}: {content[:]}...")
            
            return "\n".join(context_parts) if context_parts else ""
            
        except Exception as e:
            logger.log_err(f"获取{role}上下文失败: {e}")
            return ""
    
    def add_knowledge(self, content: str, metadata: Dict[str, Any] = None) -> bool:
        """添加知识到RAG系统"""
        try:
            chunks = self.doc_processor.chunk_text(content, metadata)
            return self.vector_db.add_documents(chunks)
        except Exception as e:
            logger.log_err(f"添加知识失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取RAG系统统计信息"""
        stats = {
            "rag_available": DEPENDENCIES_AVAILABLE,
            "config": self.config,
            "cache_size": len(self._knowledge_cache)
        }
        
        if DEPENDENCIES_AVAILABLE:
            stats.update(self.vector_db.get_stats())
        
        return stats


# ==================== 全局实例 ====================

_rag_manager = None

def get_rag_manager() -> RAGManager:
    """获取全局RAG管理器实例"""
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = RAGManager()
        _rag_manager.initialize()
    return _rag_manager


# ==================== 便捷函数 ====================

def retrieve_battle_context(attacker, defender, weapon_types: List[str] = None) -> str:
    """便捷函数：获取战斗上下文"""
    try:
        rag = get_rag_manager()
        return rag.get_battle_context(attacker, defender, weapon_types)
    except Exception as e:
        logger.log_err(f"检索战斗上下文失败: {e}")
        return ""

def retrieve_character_context(character, weapon_info: Dict[str, Any] = None, role: str = "角色") -> str:
    """便捷函数：为单个角色检索相关上下文
    
    Args:
        character: 角色对象
        weapon_info: 武器信息字典
        role: 角色类型（用于日志）
        
    Returns:
        str: 检索到的上下文文本
    """
    try:
        rag = get_rag_manager()
        return rag.get_character_context(character, weapon_info, role)
    except Exception as e:
        logger.log_err(f"检索{role}上下文失败: {e}")
        return ""

def add_battle_knowledge(content: str, source: str = "manual") -> bool:
    """便捷函数：添加战斗知识"""
    try:
        rag = get_rag_manager()
        metadata = {"source": source, "type": "battle_knowledge"}
        return rag.add_knowledge(content, metadata)
    except Exception as e:
        logger.log_err(f"添加战斗知识失败: {e}")
        return False 