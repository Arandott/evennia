"""
LLM 客户端配置示例
==============

这个文件包含了各种 LLM API 的配置示例。
将这些配置添加到你的 mygame/server/conf/settings.py 文件中。

注意：不要直接导入这个文件，而是复制相关配置到 settings.py 中。
"""

# ======================
# 本地 text-generation-webui 配置（默认）
# ======================

# 本地服务器配置
LOCAL_TEXTGEN_CONFIG = {
    "LLM_API_TYPE": "",  # 空字符串表示本地模式
    "LLM_HOST": "http://127.0.0.1:5000",
    "LLM_PATH": "/api/v1/generate",
    "LLM_HEADERS": {"Content-Type": ["application/json"]},
    "LLM_PROMPT_KEYNAME": "prompt",
    "LLM_REQUEST_BODY": {
        "max_new_tokens": 250,
        "temperature": 0.7,
        "do_sample": True,
        "top_p": 0.9,
        "typical_p": 1,
        "repetition_penalty": 1.1,
    },
}

# ======================
# OpenAI API 配置
# ======================

OPENAI_CONFIG = {
    "LLM_API_TYPE": "openai",
    "LLM_API_KEY": "your-openai-api-key-here",  # 在此填入你的 API 密钥
    "LLM_MODEL": "gpt-3.5-turbo",  # 或者 "gpt-4", "gpt-4-turbo" 等
    "LLM_HOST": "https://api.openai.com",
    "LLM_PATH": "/v1/chat/completions",
    "LLM_HEADERS": {"Content-Type": ["application/json"]},
    "LLM_REQUEST_BODY": {
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_tokens": 250,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
    },
}

# ======================
# DeepSeek API 配置
# ======================

DEEPSEEK_CONFIG = {
    "LLM_API_TYPE": "openai",  # DeepSeek 使用 OpenAI 兼容格式
    "LLM_API_KEY": "your-deepseek-api-key-here",  # 在此填入你的 DeepSeek API 密钥
    "LLM_MODEL": "deepseek-chat",
    "LLM_HOST": "https://api.deepseek.com",
    "LLM_PATH": "/v1/chat/completions",
    "LLM_HEADERS": {"Content-Type": ["application/json"]},
    "LLM_REQUEST_BODY": {
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 250,
        "top_p": 0.95,
        "frequency_penalty": 0,
        "presence_penalty": 0,
    },
}

# ======================
# Anthropic Claude API 配置（如果将来支持）
# ======================

# 注意：Claude API 格式与 OpenAI 不同，当前版本不支持
# 这里提供配置示例供将来扩展使用
CLAUDE_CONFIG_EXAMPLE = {
    "LLM_API_TYPE": "claude",  # 将来可能支持
    "LLM_API_KEY": "your-anthropic-api-key-here",
    "LLM_MODEL": "claude-3-haiku-20240307",
    "LLM_HOST": "https://api.anthropic.com",
    "LLM_PATH": "/v1/messages",
    "LLM_HEADERS": {
        "Content-Type": ["application/json"],
        "anthropic-version": ["2023-06-01"]
    },
}

# ======================
# 其他 OpenAI 兼容服务配置示例
# ======================

# 阿里云通义千问（如果提供 OpenAI 兼容接口）
QWEN_CONFIG_EXAMPLE = {
    "LLM_API_TYPE": "openai",
    "LLM_API_KEY": "your-qwen-api-key-here",
    "LLM_MODEL": "qwen-turbo",
    "LLM_HOST": "https://dashscope.aliyuncs.com/compatible-mode",
    "LLM_PATH": "/v1/chat/completions",
    "LLM_HEADERS": {"Content-Type": ["application/json"]},
    "LLM_REQUEST_BODY": {
        "model": "qwen-turbo",
        "temperature": 0.7,
        "max_tokens": 250,
    },
}

# 智谱 AI ChatGLM（如果提供 OpenAI 兼容接口）
CHATGLM_CONFIG_EXAMPLE = {
    "LLM_API_TYPE": "openai",
    "LLM_API_KEY": "your-zhipu-api-key-here",
    "LLM_MODEL": "glm-4",
    "LLM_HOST": "https://open.bigmodel.cn",
    "LLM_PATH": "/api/paas/v4/chat/completions",
    "LLM_HEADERS": {"Content-Type": ["application/json"]},
    "LLM_REQUEST_BODY": {
        "model": "glm-4",
        "temperature": 0.7,
        "max_tokens": 250,
    },
}

# ======================
# 完整的 settings.py 配置示例
# ======================

"""
将以下配置添加到你的 mygame/server/conf/settings.py 文件中：

# ========== LLM 配置 ==========

# 选择你要使用的配置（取消注释其中一个）：

# 1. 使用 OpenAI API
LLM_API_TYPE = "openai"
LLM_API_KEY = "sk-your-actual-openai-api-key-here"  # 替换为实际的 API 密钥
LLM_MODEL = "gpt-3.5-turbo"
LLM_HOST = "https://api.openai.com"
LLM_PATH = "/v1/chat/completions"
LLM_HEADERS = {"Content-Type": ["application/json"]}
LLM_REQUEST_BODY = {
    "model": "gpt-3.5-turbo",
    "temperature": 0.7,
    "max_tokens": 250,
}

# 2. 使用 DeepSeek API
# LLM_API_TYPE = "openai"
# LLM_API_KEY = "sk-your-actual-deepseek-api-key-here"  # 替换为实际的 API 密钥
# LLM_MODEL = "deepseek-chat"
# LLM_HOST = "https://api.deepseek.com"
# LLM_PATH = "/v1/chat/completions"
# LLM_HEADERS = {"Content-Type": ["application/json"]}
# LLM_REQUEST_BODY = {
#     "model": "deepseek-chat",
#     "temperature": 0.7,
#     "max_tokens": 250,
# }

# 3. 使用本地 text-generation-webui（默认）
# LLM_API_TYPE = ""  # 空字符串表示本地模式
# LLM_HOST = "http://127.0.0.1:5000"
# LLM_PATH = "/api/v1/generate"
# LLM_HEADERS = {"Content-Type": ["application/json"]}
# LLM_PROMPT_KEYNAME = "prompt"
# LLM_REQUEST_BODY = {
#     "max_new_tokens": 250,
#     "temperature": 0.7,
# }

# NPC 对话前缀（可选）
LLM_PROMPT_PREFIX = (
    "你正在扮演{name}，{desc}，位于{location}。"
    "用简短的句子回答。只以{name}的身份回应。"
    "从现在开始，{name}和{character}之间的对话开始了。"
)

""" 