"""
Thin wrapper around your existing LLMClient, specialised for battle narration.
"""
import random
import sys
import traceback
import json, textwrap
from twisted.internet.defer import inlineCallbacks, returnValue, CancelledError
from twisted.internet import reactor
from evennia.utils import logger
from evennia.contrib.rpg.llm import LLMClient   # 复用你写好的
from .rag_system import retrieve_battle_context, get_rag_manager
from .rag_system import retrieve_character_context

# Rich库导入 - 用于美化战斗叙述输出
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.columns import Columns
from rich.box import ROUNDED, HEAVY, SIMPLE
from rich.padding import Padding
from rich import box

_llm = None
def get_llm():
    global _llm
    if not _llm:
        _llm = LLMClient()
    return _llm


# -------------- Rich主题配置 ------------------

# Rich颜色主题映射
RICH_COLORS = {
    "sword": "bright_white",     # 剑光如雪
    "magic": "bright_magenta",   # 法术玄奥
    "fire": "bright_red",        # 烈火燃烧
    "ice": "bright_cyan",        # 寒冰刺骨
    "critical": "bright_yellow", # 暴击金光
    "poison": "green",           # 毒素
    "lightning": "yellow",       # 雷电
    "wind": "cyan",              # 风系
    "earth": "brown",            # 土系
    "healing": "bright_green",   # 治疗
}

# 招式图标映射
MOVE_ICONS = {
    "sword": "⚔️",      # 剑
    "magic": "🔮",      # 魔法
    "fire": "🔥",       # 火
    "ice": "❄️",        # 冰
    "lightning": "⚡",  # 雷
    "wind": "💨",       # 风
    "earth": "🪨",      # 土
    "healing": "💚",    # 治疗
    "critical": "💥",   # 暴击
    "default": "🗡️"    # 默认
}

# -------------- 颜色系统 ------------------

# 叙述文本的随机颜色池
NARRATIVE_COLORS = [
    "|c",  # 青色 - 清新
    "|m",  # 紫色 - 神秘  
    "|b",  # 蓝色 - 深邃
    "|y",  # 黄色 - 明亮
    "|g",  # 绿色 - 生机
    "|w",  # 白色 - 纯净
    "|x",  # 灰色 - 沉稳
]

# 特殊效果颜色（武侠风格）
SPECIAL_COLORS = {
    "sword": "|W",     # 亮白 - 剑光如雪
    "magic": "|M",     # 亮紫 - 法术玄奥
    "fire": "|R",      # 亮红 - 烈火燃烧
    "ice": "|C",       # 亮青 - 寒冰刺骨
    "critical": "|Y",  # 亮黄 - 暴击金光
}

def get_random_narrative_color():
    """获取随机叙述颜色"""
    return random.choice(NARRATIVE_COLORS)

def get_health_color(health_percent):
    """
    根据血量百分比获取颜色
    
    Args:
        health_percent (float): 血量百分比 (0.0 - 1.0)
    
    Returns:
        str: Evennia颜色代码
    """
    if health_percent >= 0.8:
        return "|g"      # 绿色 - 健康
    elif health_percent >= 0.6:
        return "|G"      # 亮绿 - 良好
    elif health_percent >= 0.4:
        return "|y"      # 黄色 - 警告
    elif health_percent >= 0.2:
        return "|Y"      # 亮黄 - 危险
    elif health_percent > 0:
        return "|r"      # 红色 - 濒死
    else:
        return "|R"      # 亮红 - 死亡
    

def get_rich_health_color(health_percent):
    """
    根据血量百分比获取Rich颜色
    
    Args:
        health_percent (float): 血量百分比 (0.0 - 1.0)
    
    Returns:
        str: Rich颜色名称
    """
    if health_percent >= 0.8:
        return "bright_green"    # 健康
    elif health_percent >= 0.6:
        return "green"           # 良好
    elif health_percent >= 0.4:
        return "yellow"          # 警告
    elif health_percent >= 0.2:
        return "orange1"         # 危险
    elif health_percent > 0:
        return "red"             # 濒死
    else:
        return "bright_red"      # 死亡

def detect_move_type(move_name, narrative):
    """
    检测招式类型，用于选择合适的图标和颜色
    
    Args:
        move_name (str): 招式名称
        narrative (str): 叙述内容
        
    Returns:
        str: 招式类型
    """
    move_text = f"{move_name} {narrative}".lower()
    
    # 招式类型关键词检测
    type_keywords = {
        "fire": ["火", "炎", "焰", "烈", "灼", "燃"],
        "ice": ["冰", "寒", "霜", "雪", "冻", "凝"],
        "lightning": ["雷", "电", "闪", "击", "轰"],
        "wind": ["风", "气", "飘", "旋", "刃"],
        "earth": ["土", "石", "岩", "山", "地"],
        "magic": ["法", "术", "咒", "魔", "灵", "法杖"],
        "sword": ["剑", "刀", "刃", "锋", "斩"],
        "critical": ["暴击", "重击", "致命", "绝杀"],
        "healing": ["治疗", "恢复", "愈", "疗"],
    }
    
    for move_type, keywords in type_keywords.items():
        if any(keyword in move_text for keyword in keywords):
            return move_type
    
    return "default"


def get_health_status_text(health_percent):
    """
    根据血量百分比获取状态描述
    
    Args:
        health_percent (float): 血量百分比 (0.0 - 1.0)
    
    Returns:
        str: 状态描述
    """
    if health_percent >= 0.9:
        return "毫发无损"
    elif health_percent >= 0.75:
        return "略有损伤"
    elif health_percent >= 0.5:
        return "伤势不轻"
    elif health_percent >= 0.25:
        return "伤痕累累"
    elif health_percent > 0:
        return "命悬一线"
    else:
        return "败北倒地"
    
# -------------- prompt builder (RAG hook ready) ------------------

BATTLE_SYS_PROMPT = textwrap.dedent("""
你是一名小说旁白大师，语气豪迈、画面感强。你的输出需要结合角色描述和武器描述，以及提供的背景知识，进行合理的想象。
输出要求如下：
- 想象规则如下：第一，如果遇到没什么特色的角色，请你使用武侠风格；第二，如果遇到网球运动员，请你使用网球风格；第三，如果遇到忍者，请你使用忍者风格；第四，如果遇到法师，请你使用魔法风格；以此类推。
- 在 <battle/> 标签里提供的战斗结果已经定死，不得修改。
- 分别参考 <attacker_context/> 和 <defender_context/> 标签中的背景知识来丰富对攻击者和防御者的描述，但不要生硬地复制。
- 如果有 <additional_context/> 标签，也要参考其中的额外背景信息。
- 输出必须为 JSON，键为 move_name, narrative, effect。不要附加多余字段。
- move_name 必须为招式名称，不要使用"招式"、"技能"等字眼，并且要符合角色特征。
- narrative中必须包含一个招式名字，并以【】包裹，但不要过于生硬。
- effect也是一句话，其中除了描述外，必须包含伤害值。
- 只返回 JSON，本行重要：**不要**用 ``` 包裹。
- 角色姓名以占位符 <<A>> (攻击者) / <<D>> (防御者) 出现，不得改写或音译。
""").strip()

# ---------- constants ----------
NAME_PLC = {"attacker": "<<A>>",
            "defender": "<<D>>"}

def calculate_health_info(character, damage):
    """
    计算角色的血量信息
    
    Args:
        character: 角色对象
        damage: 即将造成的伤害
    
    Returns:
        dict: 包含血量信息的字典
    """
    try:
        current_hp = getattr(character.db, 'hp', 100)
        max_hp = getattr(character.db, 'max_hp', 100)
        
        # 血量比例
        hp = current_hp / max_hp if max_hp > 0 else 0
        
        return {
            "current_hp": current_hp,
            "max_hp": max_hp,
            "hp": hp,
            "damage": damage,
            "status": get_health_status_text(hp)
        }
    except Exception as e:
        logger.log_warn(f"计算血量信息失败: {e}")
        return {
            "current_hp": 100,
            "max_hp": 100,
            "hp": 0.8,
            "damage": damage,
            "status": "健康",
        }

def safe_get_character_info(character, default_desc, role="角色"):
    """
    安全获取角色信息，包括描述和武器
    
    Args:
        character: 角色对象
        default_desc: 默认描述
        role: 角色类型（用于日志）
    
    Returns:
        tuple: (描述, 武器信息字典)
    """
    try:
        # 获取基础描述
        if character.db.desc:
            desc = character.db.desc or default_desc
        else:
            desc = default_desc
        
        # 获取武器信息
        weapon_info = {
            "name": "赤手空拳",
            "type": "unarmed",
            "desc": "空手搏击",
            "type_name": "空手"
        }
        
        # 检查是否有装备系统
        if hasattr(character, 'equipment'):
            try:
                weapon = character.equipment.get_weapon()
                if weapon:
                    # 获取武器基本信息
                    weapon_name = weapon.key
                    weapon_type_key = getattr(weapon.db, 'weapon_type', 'sword')
                    weapon_desc = getattr(weapon.db, 'desc', f"一把{weapon_name}")
                    
                    # 获取武器类型中文名
                    from .weapon import WEAPON_TYPES
                    weapon_type_data = WEAPON_TYPES.get(weapon_type_key, WEAPON_TYPES["sword"])
                    weapon_type_name = weapon_type_data["name"]
                   
                    weapon_info = {
                        "name": weapon_name,
                        "type": weapon_type_key,
                        "type_name": weapon_type_name,
                        "desc": weapon_desc,
                    }
                    
                    logger.log_info(f"{role}武器信息: {weapon_info}")
                    
            except Exception as e:
                logger.log_warn(f"获取{role}武器信息失败: {e}")
        
        return desc, weapon_info
        
    except Exception as e:
        logger.log_err(f"获取{role}信息失败: {e}")
        return default_desc, weapon_info


def build_battle_prompt(attacker, defender, hit, dmg, room, context=""):
    hit_text = "命中" if hit else "未命中"
    
    # ① 角色简介
    attacker_desc, attacker_weapon = safe_get_character_info(
        attacker, "青衫俊朗的剑客", "攻击者"
    )
    defender_desc, defender_weapon = safe_get_character_info(
        defender, "面容冷峻的刀客", "防御者"
    )
    
    defender_health = calculate_health_info(defender, dmg)
    
    logger.log_info(f"攻击者武器: {attacker_weapon}")
    logger.log_info(f"防御者武器: {defender_weapon}")
    
    # ② RAG上下文检索 - 分别为攻击者和防御者检索
    try:
        # 为攻击者检索相关上下文
        attacker_context = retrieve_character_context(attacker, attacker_weapon, "攻击者")
        
        # 为防御者检索相关上下文
        defender_context = retrieve_character_context(defender, defender_weapon, "防御者")
        
        logger.log_info(f"攻击者上下文长度: {len(attacker_context)}")
        logger.log_info(f"防御者上下文长度: {len(defender_context)}")
        
    except Exception as e:
        logger.log_warn(f"RAG角色上下文检索失败: {e}")
        attacker_context = ""
        defender_context = ""
    
    char_tag = (
        "<chars>\n"
        f"{NAME_PLC['attacker']}: {attacker_desc}\n"
        f"  武器: {attacker_weapon['name']}（{attacker_weapon['type_name']}）- {attacker_weapon['desc']}\n"
        f"{NAME_PLC['defender']}: {defender_desc}\n"
        f"  武器: {defender_weapon['name']}（{defender_weapon['type_name']}）- {defender_weapon['desc']}\n"
        f"  当前状态: {defender_health['status']}（血量{defender_health['hp']:.0%}）\n"
        "</chars>"
    )
    
    battle_tag = (
        f"<battle>\n"
        f"- 场景: {room.key}\n"
        f"- 攻击者: {NAME_PLC['attacker']}\n"
        f"- 防御者: {NAME_PLC['defender']}\n"
        f"- 结果: {hit_text}\n"
        f"- 伤害: {dmg}\n"
        f"</battle>"
    )
    
    # ③ 添加分别检索的RAG上下文
    context_tag = ""
    
    # 攻击者上下文
    if attacker_context:
        context_tag += f"\n<attacker_context>\n{NAME_PLC['attacker']}相关背景知识：\n{attacker_context}\n</attacker_context>"
    
    # 防御者上下文
    if defender_context:
        context_tag += f"\n<defender_context>\n{NAME_PLC['defender']}相关背景知识：\n{defender_context}\n</defender_context>"
    
    # ④ 添加用户提供的额外上下文
    if context:
        context_tag += f"\n<additional_context>\n{context}\n</additional_context>"
    
    return [BATTLE_SYS_PROMPT, char_tag, battle_tag + context_tag]   # list ➟ llm_client 会拼成多行


# ---------- helper: substitute placeholders ----------
def _post_replace(text: str, attacker, defender) -> str:
    return (text
            .replace(NAME_PLC["attacker"], attacker.key)
            .replace(NAME_PLC["defender"], defender.key))
    
def format_battle_output_rich(narrative, effect, move_name, attacker, defender, hit, dmg):
    """
    使用Rich库格式化战斗输出，创建美观的战斗叙述面板
    
    Args:
        narrative (str): LLM生成的叙述
        effect (str): LLM生成的效果描述
        move_name (str): 招式名称
        attacker: 攻击者
        defender: 防御者
        hit (bool): 是否命中
        dmg (int): 伤害值
    
    Returns:
        str: Rich格式化后的输出
    """
    try:
        # 替换占位符
        narrative = _post_replace(narrative, attacker, defender)
        effect = _post_replace(effect, attacker, defender)
        move_name = _post_replace(move_name, attacker, defender)
        
        # 创建Rich控制台
        console = Console(width=80, force_terminal=True, emoji=True)
        
        # 检测招式类型
        move_type = detect_move_type(move_name, narrative)
        move_icon = MOVE_ICONS.get(move_type, MOVE_ICONS["default"])
        move_color = RICH_COLORS.get(move_type, "white")
        
        # 计算防御者血量信息
        defender_health = calculate_health_info(defender, dmg if hit else 0)
        health_color = get_rich_health_color(defender_health['hp'])
        
        # ===== 创建招式标题 =====
        move_title = Text()
        move_title.append(move_icon + " ", style="bold")
        move_title.append(move_name, style=f"bold {move_color}")
        
        # ===== 使用字符串构建内容，而不是Rich对象 =====
        content_lines = []
        
        # 叙述部分（居中对齐）
        narrative_line = f"[{move_color}]{narrative}[/{move_color}]"
        content_lines.append(narrative_line.center(76))  # 76是面板内容宽度
        content_lines.append("")  # 空行
        
        # 效果部分
        if hit:
            effect_line = f"[bold red]💥[/bold red] [bold {health_color}]{effect}[/bold {health_color}]"
        else:
            effect_line = f"[bold yellow]💨[/bold yellow] [bold yellow]{effect}[/bold yellow]"
        
        content_lines.append(effect_line.center(76))
        content_lines.append("")  # 空行
        
        # 血量信息
        if hit and dmg > 0:
            hp_after = max(0, defender_health['current_hp'])
            hp_percent_after = hp_after / defender_health['max_hp'] if defender_health['max_hp'] > 0 else 0
            
            # 血量变化
            hp_change_line = f"[bold]{defender.key}:[/bold] [green]{defender_health['current_hp'] + dmg}[/green] [dim]→[/dim] [{health_color}]{hp_after}[/{health_color}][dim]/{defender_health['max_hp']}[/dim]"
            content_lines.append(hp_change_line.center(76))
            
            # 血量条
            bar_length = 70 /  defender_health['max_hp']
            filled_length = int(bar_length * defender_health['current_hp'])
            empty_length = int(bar_length * defender_health['max_hp']) - filled_length
            hp_bar_line = f"[bold red]♥[/bold red] [{health_color}]{'█' * filled_length}[/{health_color}][dim]{'░' * empty_length}[/dim]"
            content_lines.append(hp_bar_line.center(76))
        else:
            hp_info_line = f"[dim]{defender.key} 未受伤害[/dim]"
            content_lines.append(hp_info_line.center(76))
        
        # ===== 创建面板内容 =====
        panel_content = "\n".join(content_lines)
        
        # ===== 创建面板 =====
        border_style = move_color if hit else "yellow"
        
        panel = Panel(
            panel_content,
            title=move_title,
            border_style=border_style,
            box=ROUNDED,
            padding=(0, 1),
            width=78
        )
        
        # ===== 渲染为字符串 =====
        with console.capture() as capture:
            console.print(panel)
        
        return capture.get()
        
    except Exception as e:
        logger.log_err(f"Rich格式化输出失败: {e}")
        import traceback
        logger.log_err(f"详细错误: {traceback.format_exc()}")
        # 回退到简单格式
        return format_battle_output_simple(narrative, effect, attacker, defender, hit, dmg)
    

def format_battle_output_simple(narrative, effect, attacker, defender, hit, dmg):
    """
    简单格式化战斗输出（后备方案）
    
    Args:
        narrative (str): LLM生成的叙述
        effect (str): LLM生成的效果描述
        attacker: 攻击者
        defender: 防御者
        hit (bool): 是否命中
        dmg (int): 伤害值
    
    Returns:
        str: 格式化后的输出
    """
    try:
        # 替换占位符
        narrative = _post_replace(narrative, attacker, defender)
        effect = _post_replace(effect, attacker, defender)
        
        # 获取随机叙述颜色
        narrative_color = get_random_narrative_color()
        
        # 根据血量计算效果颜色
        defender_health = calculate_health_info(defender, dmg if hit else 0)
        effect_color = get_health_color(defender_health['hp'])
        
        # 特殊情况的颜色处理
        if dmg > 30:  # 高伤害
            effect_color = SPECIAL_COLORS.get("critical", effect_color)
        elif "暴击" in narrative or "重击" in narrative:
            effect_color = SPECIAL_COLORS.get("critical", effect_color)
        elif "法术" in narrative or "法杖" in narrative:
            narrative_color = SPECIAL_COLORS.get("magic", narrative_color)
        
        # 格式化输出
        formatted_narrative = f"{narrative_color}{narrative}|n"
        formatted_effect = f"{effect_color}({effect})|n"
        
        return f"{formatted_narrative} {formatted_effect}"
        
    except Exception as e:
        logger.log_err(f"简单格式化输出失败: {e}")
        # 最后的后备格式化
        simple_narrative = _post_replace(narrative, attacker, defender)
        simple_effect = _post_replace(effect, attacker, defender)
        return f"|c{simple_narrative}|n |y({simple_effect})|n"


def format_battle_output(narrative, effect, attacker, defender, hit, dmg, move_name="未知招式"):
    """
    主要的战斗输出格式化函数，会尝试使用Rich，失败时回退到简单格式
    
    Args:
        narrative (str): LLM生成的叙述
        effect (str): LLM生成的效果描述
        attacker: 攻击者
        defender: 防御者
        hit (bool): 是否命中
        dmg (int): 伤害值
        move_name (str): 招式名称
    
    Returns:
        str: 格式化后的输出
    """
    try:
        # 优先尝试Rich格式化
        return format_battle_output_rich(narrative, effect, move_name, attacker, defender, hit, dmg)
    except Exception as e:
        logger.log_warn(f"Rich格式化失败，使用简单格式: {e}")
        # 回退到简单格式
        return format_battle_output_simple(narrative, effect, attacker, defender, hit, dmg)

# -------------- DeepSeek call & safe-parsing ---------------------

@inlineCallbacks
def llm_narrate_sync(attacker, defender, hit, dmg, room, timeout=80.0):
    """
    同步LLM叙述，带超时保护
    
    Args:
        timeout (float): 超时时间（秒），默认3秒
        
    Returns:
        str: 叙述文本，超时或失败时返回简单描述
    """
    raw = None  # ✅ 在作用域开始就定义
    timeout_d = None
    try:
        prompt = build_battle_prompt(attacker, defender, hit, dmg, room)
        logger.log_info(f"LLM prompt: {prompt}")
        
        # 创建带超时的deferred
        d = get_llm().get_response(prompt)
        timeout_d = reactor.callLater(timeout, d.cancel)
        
        try:
            raw = yield d
            timeout_d.cancel()  # 成功了，取消超时
        except:
            # 超时或其他错误
            raise TimeoutError("LLM call timed out")
            
        # 解析结果
        data = json.loads(raw)
        narrative = data.get("narrative", "")
        effect = data.get("effect", "")
        move_name = data.get("move_name", "未知招式")
        
        if not narrative:
            raise ValueError("empty narrative")
        
        # formatted = _post_replace(f"|c{narrative}|n |y({effect})|n",
        #                           attacker, defender)
        
        formatted = format_battle_output(narrative, effect, attacker, defender, hit, dmg, move_name)
            
        returnValue(formatted)
        
    except TimeoutError:             # 真实超时
        logger.log_warn(f"LLM narration timed out after {timeout}s")

    except (json.JSONDecodeError, ValueError) as e:
        logger.log_err(f"LLM narration JSON error: {e} | Raw: {raw[:]}...")

    except Exception as e:             # 网络错误等
        logger.log_err(f"LLM narration unknown failure: {e}")
        logger.log_err(f"Exception type: {type(e).__name__}")
        logger.log_err(f"Exception args: {e.args}")
        
        # 🔍 完整的堆栈跟踪
        tb_lines = traceback.format_exc().split('\n')
        logger.log_err(f"Full traceback:")
        for i, line in enumerate(tb_lines):
            if line.strip():
                logger.log_err(f"  {i:2d}: {line}")
        
        # 🔍 当前帧信息
        frame = sys.exc_info()[2].tb_frame
        logger.log_err(f"Error occurred in function: {frame.f_code.co_name}")
        logger.log_err(f"Error occurred at line: {sys.exc_info()[2].tb_lineno}")
        logger.log_err(f"Local variables at error:")
        for var_name, var_value in frame.f_locals.items():
            try:
                logger.log_err(f"  {var_name} = {repr(var_value)[:100]}")
            except:
                logger.log_err(f"  {var_name} = <repr failed>")
        
    # 超时或失败时的快速后备
    if hit:
        fallback = f"|c{attacker.key} 的攻击命中了 {defender.key}！|n |y(造成 {dmg} 点伤害)|n"
    else:
        fallback = f"|c{attacker.key} 的攻击被 {defender.key} 躲避了！|n |y(未造成伤害)|n"
    
    returnValue(fallback)

# -------------- 异步增强版本 ---------------------

@inlineCallbacks  
def llm_narrate_async(attacker, defender, hit, dmg, room, context=""):
    """异步版本，用于非关键叙述增强"""
    try:
        prompt = build_battle_prompt(attacker, defender, hit, dmg, room, context)
        raw = yield get_llm().get_response(prompt)
        data = json.loads(raw)
        narrative = data.get("narrative", "")
        effect = data.get("effect", "")
        formatted = _post_replace(f"|c{narrative}|n |y({effect})|n",
                                  attacker, defender)
        returnValue(formatted)
    except Exception as e:
        logger.log_trace(f"Async LLM narration failed: {e}")
        returnValue("")  # 异步失败就不显示了
