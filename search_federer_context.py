#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import weaviate
import textwrap
from langchain_community.embeddings import ZhipuAIEmbeddings

def search_federer_context():
    """使用费德勒描述在BattleKnowledge collection中查找相关上下文"""
    
    # 连接到本地Weaviate实例
    client = weaviate.connect_to_local(
        host="localhost", 
        port=8080, 
        grpc_port=50051
    )
    
    try:
        # 初始化智谱AI embedding模型（与notebook中保持一致）
        embedder = ZhipuAIEmbeddings(
            model="embedding-3",
            dimensions=1024,
            api_key="8725cd11e5cc4c56aabc5142442e59f6.IceSidZVpsp39Mj3"
        )
        
        # 查询文本
        query_text = "罗杰·费德勒（Roger Federer，1981 年生）被誉为史上最杰出的男子网球选手之一，职业生涯共夺得 20 座大满贯单打冠军、103 个 ATP 单打冠军，并累积 310 周世界第一（其中连续 237 周创纪录）"
        
        print("=== 搜索查询 ===")
        print(f"查询文本: {query_text}")
        print()
        
        # 生成查询向量
        query_vector = embedder.embed_query(query_text)
        print(f"查询向量维度: {len(query_vector)}")
        print()
        
        # 获取BattleKnowledge collection
        collection = client.collections.get("BattleKnowledge")
        
        # 执行向量相似性搜索
        response = collection.query.near_vector(
            near_vector=query_vector,
            limit=5,  # 返回最相关的5个结果
            return_metadata=["score"]  # 返回相似度分数
        )
        
        print("=== 搜索结果 ===")
        print(f"找到 {len(response.objects)} 个相关结果:\n")
        
        for i, obj in enumerate(response.objects, 1):
            # 获取相似度分数
            score = obj.metadata.score if obj.metadata and obj.metadata.score else "N/A"
            
            print(f"--- 结果 {i} (相似度: {score:.4f}) ---")
            
            # 获取内容并格式化显示
            content = obj.properties.get("content", "无内容")
            
            # 使用textwrap格式化长文本
            wrapped_content = textwrap.fill(content, width=80, 
                                          initial_indent="  ", 
                                          subsequent_indent="  ")
            print(wrapped_content)
            print()
        
        # 显示collection的总体信息
        total_objects = collection.aggregate.over_all().total_count
        print(f"=== Collection信息 ===")
        print(f"BattleKnowledge collection总对象数: {total_objects}")
        print("搜索完成！")
        
    except Exception as e:
        print(f"搜索过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 关闭连接
        client.close()

if __name__ == "__main__":
    search_federer_context() 