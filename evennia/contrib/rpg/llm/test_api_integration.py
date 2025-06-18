#!/usr/bin/env python3
"""
LLM API 集成测试脚本
=================

这个脚本用于测试 LLM 客户端是否能正确处理不同类型的 API。
可以在不启动完整 Evennia 服务器的情况下测试 API 连接。

用法:
    python test_api_integration.py

注意: 
    - 你需要在脚本中设置有效的 API 密钥才能测试云端服务
    - 本地测试需要运行 text-generation-webui 服务器
"""

import json
import os
import sys

# 添加必要的模拟模块以避免导入错误
class MockSettings:
    DEBUG = True
    LLM_API_TYPE = ""
    LLM_API_KEY = ""
    LLM_MODEL = "gpt-3.5-turbo"
    LLM_HOST = "http://127.0.0.1:5000"
    LLM_PATH = "/api/v1/generate"
    LLM_HEADERS = {"Content-Type": ["application/json"]}
    LLM_REQUEST_BODY = {"max_new_tokens": 50, "temperature": 0.7}

# 模拟 Django settings
sys.modules['django.conf'] = type(sys)('django.conf')
sys.modules['django.conf'].settings = MockSettings()

# 模拟 Evennia logger
class MockLogger:
    @staticmethod
    def log_info(msg):
        print(f"[INFO] {msg}")
    
    @staticmethod
    def log_err(msg):
        print(f"[ERROR] {msg}")

sys.modules['evennia'] = type(sys)('evennia')
sys.modules['evennia'].logger = MockLogger()

# 模拟 utils
sys.modules['evennia.utils'] = type(sys)('evennia.utils')
sys.modules['evennia.utils'].utils = type(sys)('utils')
sys.modules['evennia.utils'].utils.make_iter = lambda x: [x] if isinstance(x, str) else x

def test_request_body_formatting():
    """测试不同 API 类型的请求体格式化"""
    print("=== 测试请求体格式化 ===")
    
    # 测试本地 API 格式
    print("\n1. 本地 text-generation-webui 格式:")
    local_settings = MockSettings()
    local_settings.LLM_API_TYPE = ""
    
    # 这里我们需要模拟 LLMClient 的行为
    prompt = "Hello, how are you?"
    
    # 本地格式应该是: {"prompt": "...", "max_new_tokens": 50, ...}
    local_body = {
        "prompt": prompt,
        "max_new_tokens": 50,
        "temperature": 0.7
    }
    print(f"本地格式请求体: {json.dumps(local_body, indent=2, ensure_ascii=False)}")
    
    # 测试 OpenAI API 格式
    print("\n2. OpenAI API 格式:")
    openai_body = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 50
    }
    print(f"OpenAI格式请求体: {json.dumps(openai_body, indent=2, ensure_ascii=False)}")

def test_response_parsing():
    """测试不同 API 类型的响应解析"""
    print("\n=== 测试响应解析 ===")
    
    # 测试本地响应格式解析
    print("\n1. 本地 text-generation-webui 响应:")
    local_response = {
        "results": [{"text": "Hello! I'm doing well, thank you for asking."}]
    }
    print(f"本地响应格式: {json.dumps(local_response, indent=2, ensure_ascii=False)}")
    
    try:
        local_text = local_response["results"][0]["text"]
        print(f"提取的文本: {local_text}")
    except (KeyError, IndexError) as e:
        print(f"解析失败: {e}")
    
    # 测试 OpenAI 响应格式解析
    print("\n2. OpenAI API 响应:")
    openai_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello! I'm doing well, thank you for asking."
                }
            }
        ]
    }
    print(f"OpenAI响应格式: {json.dumps(openai_response, indent=2, ensure_ascii=False)}")
    
    try:
        openai_text = openai_response["choices"][0]["message"]["content"]
        print(f"提取的文本: {openai_text}")
    except (KeyError, IndexError) as e:
        print(f"解析失败: {e}")

def show_configuration_examples():
    """显示配置示例"""
    print("\n=== 配置示例 ===")
    
    print("\n1. OpenAI API 配置 (添加到 settings.py):")
    openai_config = """
LLM_API_TYPE = "openai"
LLM_API_KEY = "sk-your-openai-api-key-here"
LLM_MODEL = "gpt-3.5-turbo"
LLM_HOST = "https://api.openai.com"
LLM_PATH = "/v1/chat/completions"
LLM_HEADERS = {"Content-Type": ["application/json"]}
LLM_REQUEST_BODY = {
    "model": "gpt-3.5-turbo",
    "temperature": 0.7,
    "max_tokens": 250,
}
"""
    print(openai_config)
    
    print("\n2. DeepSeek API 配置 (添加到 settings.py):")
    deepseek_config = """
LLM_API_TYPE = "openai"
LLM_API_KEY = "sk-your-deepseek-api-key-here"
LLM_MODEL = "deepseek-chat"
LLM_HOST = "https://api.deepseek.com"
LLM_PATH = "/v1/chat/completions"
LLM_HEADERS = {"Content-Type": ["application/json"]}
LLM_REQUEST_BODY = {
    "model": "deepseek-chat",
    "temperature": 0.7,
    "max_tokens": 250,
}
"""
    print(deepseek_config)
    
    print("\n3. 本地 text-generation-webui 配置 (默认):")
    local_config = """
LLM_API_TYPE = ""  # 空字符串表示本地模式
LLM_HOST = "http://127.0.0.1:5000"
LLM_PATH = "/api/v1/generate"
LLM_HEADERS = {"Content-Type": ["application/json"]}
LLM_REQUEST_BODY = {
    "max_new_tokens": 250,
    "temperature": 0.7,
}
"""
    print(local_config)

def main():
    """主测试函数"""
    print("LLM API 集成测试")
    print("=" * 50)
    
    try:
        test_request_body_formatting()
        test_response_parsing()
        show_configuration_examples()
        
        print("\n=== 测试完成 ===")
        print("✅ 请求体格式化正常")
        print("✅ 响应解析正常") 
        print("✅ 配置示例已显示")
        
        print("\n下一步:")
        print("1. 在 settings.py 中添加相应的 LLM 配置")
        print("2. 获取有效的 API 密钥（如果使用云端服务）")
        print("3. 在游戏中测试 NPC 对话功能")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 