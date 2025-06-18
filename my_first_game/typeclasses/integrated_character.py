"""
集成 Character 类：traits + clothing + turnbattle.tb_basic

此模块整理自用户提供的脚本，仅重新组织结构与注释；**不改变任何运行逻辑**。
它提供一个解决多个 contrib 系统冲突的 `CombinedCharacter`，
可直接用于 Evennia 项目中替换默认角色类。
"""

# ---------------------------------------------------------------------------
# 武器系统导入
# ---------------------------------------------------------------------------
from .weapon import EquipmentHandler, CmdEquip, CmdUnequip

# ---------------------------------------------------------------------------
# 标准库导入
# ---------------------------------------------------------------------------
from collections import defaultdict  # 当前脚本未用到，但保留以兼容外部引用
import random


# ---------------------------------------------------------------------------
# Rich 库导入 - 用于美化状态显示
# ---------------------------------------------------------------------------
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich import box

# ---------------------------------------------------------------------------
# Evennia 核心导入
# ---------------------------------------------------------------------------
from evennia import DefaultCharacter, default_cmds, Command  # DefaultCharacter 目前未直接使用，但保留
from evennia.utils import lazy_property, iter_to_str, delay, logger

# ---------------------------------------------------------------------------
# Contrib 系统导入
# ---------------------------------------------------------------------------
from evennia.contrib.rpg.traits import TraitHandler
from evennia.contrib.game_systems.clothing.clothing import get_worn_clothes
from evennia.contrib.game_systems.turnbattle.tb_basic import (
    TBBasicCharacter,
    BasicCombatRules,
    TBBasicTurnHandler,
    TURN_TIMEOUT,
    CmdFight,
    CmdAttack,
    CmdPass,
    CmdDisengage,
    CmdRest,
    CmdCombatHelp,
)

# ---------------------------------------------------------------------------
# Evennia 脚本系统
# ---------------------------------------------------------------------------
from evennia.scripts.scripts import DefaultScript

# ---------------------------------------------------------------------------
# LLM 战斗叙事系统导入
# ---------------------------------------------------------------------------
from .llm_battle_client import llm_narrate_sync, llm_narrate_async
from .rag_system import get_rag_manager, add_battle_knowledge
from twisted.internet.defer import inlineCallbacks

# ---------------------------------------------------------------------------
# 生命周期常量
# ---------------------------------------------------------------------------
STATE_ALIVE = "alive"
STATE_DEFEATED = "defeated"
STATE_RESPAWNING = "respawning"

# ---------------------------------------------------------------------------
# 自定义战斗规则
# ---------------------------------------------------------------------------
class CombinedCombatRules(BasicCombatRules):
    """扩展 `at_defeat` 行为：当角色被击败时切换至自定义状态机。"""

    def at_defeat(self, defeated):
        # 保持原有广播行为
        super().at_defeat(defeated)

        # # 触发角色状态机（若存在）
        # if hasattr(defeated, "set_state"):
        #     defeated.location.msg_contents(f"{defeated} has attr set_state")
        #     defeated.set_state(STATE_DEFEATED)
        # else:
        #     defeated.location.msg_contents(f"{defeated} does not have attr set_state")
    
    @inlineCallbacks
    def resolve_attack(self, attacker, defender, attack_value=None, defense_value=None):
        """
        Resolves an attack and outputs the result.

        Args:
            attacker (obj): Character doing the attacking
            defender (obj): Character being attacked

        Notes:
            Even though the attack and defense values are calculated
            extremely simply, they are separated out into their own functions
            so that they are easier to expand upon.
        """
        hit = False
        damage_value = 0
        
        # Get an attack roll from the attacker.
        if not attack_value:
            attack_value = self.get_attack(attacker, defender)
        # Get a defense value from the defender.
        if not defense_value:
            defense_value = self.get_defense(attacker, defender)
        
        # If the attack value is lower than the defense value, miss. Otherwise, hit.
        if attack_value < defense_value:
            pass
            # attacker.location.msg_contents("%s的攻击 attack misses %s!" % (attacker, defender))
        else:
            hit = True
            damage_value = self.get_damage(attacker, defender)  # Calculate damage value.
            # Announce damage dealt and apply damage.
            # attacker.location.msg_contents(
            #     "%s hits %s for %i damage!" % (attacker, defender, damage_value)
            # )
            self.apply_damage(defender, damage_value)
            # If defender HP is reduced to 0 or less, call at_defeat.
            if defender.db.hp <= 0:
                self.at_defeat(defender)
        
        attacker.location.msg_contents(f"{attacker} 出招！")
        # 保存当前位置引用，避免异步回调时位置已变
        text = yield llm_narrate_sync(attacker, defender, hit, damage_value, attacker.location)
        if attacker.location:
            attacker.location.msg_contents(text)


# 实例化全局规则对象
COMBINED_RULES = CombinedCombatRules()


# ---------------------------------------------------------------------------
# NPC 战斗 AI 脚本
# ---------------------------------------------------------------------------
class CombatAIScript(DefaultScript):
    """周期性检查并执行 NPC 的战斗 AI 行为。"""

    def at_script_creation(self):
        self.key = "combat_ai"
        self.interval = 3  # 每 3 秒触发一次
        self.persistent = True

    def at_repeat(self):
        if hasattr(self.obj, "ai_combat_action"):
            self.obj.ai_combat_action()
        else:
            # 如果对象不再拥有行为方法则停止脚本
            self.stop()


# ---------------------------------------------------------------------------
# 角色类：集成 traits / clothing / turnbattle
# ---------------------------------------------------------------------------
class CombinedCharacter(TBBasicCharacter):
    """结合特征、服装与基础回合制战斗的角色类型。"""

    # 覆盖默认规则
    rules = COMBINED_RULES

    # NPC 战斗 AI：动作选择概率
    combat_probabilities = {
        "attack": 0.8,      # 80% 攻击
        "pass": 0.15,       # 15% 跳过
        "disengage": 0.05,  # 5% 脱离
    }

    # ---------------------------------------------------------------------
    # Traits 接入
    # ---------------------------------------------------------------------
    @lazy_property
    def traits(self):
        """返回 TraitHandler 以支持特征系统。"""
        return TraitHandler(self)
    
    @lazy_property
    def equipment(self):
        """返回装备管理器"""
        return EquipmentHandler(self)

    # ---------------------------------------------------------------------
    # 对象创建钩子
    # ---------------------------------------------------------------------
    def at_object_creation(self):
        """角色创建时初始化属性与脚本。"""
        super().at_object_creation()

        # ---- 战斗相关拓展属性 ----
        self.db.immune_combat = False  # 是否免疫被拉入战斗
        self.db.peaceful = False       # 是否为和平 NPC（不会主动战斗）
        self.db.state = STATE_ALIVE
        self.db.death_count = 0

        # ---- HP 大小写兼容 ----
        # turnbattle 早期脚本使用 HP；此处确保 hp/HP 双字段同步存在
        if hasattr(self.db, "hp") and not hasattr(self.db, "HP"):
            self.db.HP = self.db.hp
        elif hasattr(self.db, "HP") and not hasattr(self.db, "hp"):
            self.db.hp = self.db.HP

        # ---- Traits 初始化 ----
        self.traits.add("strength", "力量", trait_type="static", base=12, mod=0)
        self.traits.add("dexterity", "敏捷", trait_type="static", base=10, mod=0)
        self.traits.add("constitution", "体质", trait_type="static", base=10, mod=0)
        self.traits.add("hp", "生命值", trait_type="gauge", base=self.db.max_hp, min=0)
        self.traits.hp.current = self.db.hp

        # ---- NPC AI 脚本 ----
        if not self.has_account and not self.scripts.has("combat_ai"):  # 仅为 NPC 添加 AI 脚本
            self.scripts.add(CombatAIScript)
            
        # ---- 装备系统初始化 ----
        self.equipment._load_equipment()

    # ------------------------------------------------------------------
    # 状态机
    # ------------------------------------------------------------------
    def set_state(self, new_state: str):
        """集中管理状态切换。"""
        current = self.db.state
        if current == new_state:
            return  # 无变化

        self.db.state = new_state

        if new_state == STATE_DEFEATED:
            self._enter_defeated()
        elif new_state == STATE_RESPAWNING:
            self._enter_respawning()
        elif new_state == STATE_ALIVE:
            self._enter_alive()

    # -------------------- 具体状态进入逻辑 --------------------
    def _enter_alive(self):
        self.location.msg_contents(f"|g{self.key} is back on their feet!|n", exclude=self)

    def _enter_defeated(self):
        self.location.msg_contents(f"|r{self.key} has been defeated!|n")
        self.rules.combat_cleanup(self)  # 清理临时战斗属性
        self.db.death_count += 1

        # 动态计算重生延迟
        base_delay = 60 if self.has_account else 300  # 玩家 vs NPC
        extra = 2 ** (self.db.death_count - 1)
        delay_time = base_delay + extra

        # 计划重生
        delay(delay_time, self.respawn)

    def _enter_respawning(self):
        # 完全恢复生命值
        self.db.hp = self.db.max_hp
        self.traits.hp.current = self.db.hp
        self.sync_hp()

        # 传送至 home
        home = self.home or self.db.default_home
        if home:
            self.move_to(home, quiet=True, move_type="respawn")

        self.rules.combat_cleanup(self)

    # ------------------------------------------------------------------
    # 生命周期辅助
    # ------------------------------------------------------------------
    def respawn(self):
        if self.db.state != STATE_DEFEATED:
            return
        self.set_state(STATE_RESPAWNING)
        self.set_state(STATE_ALIVE)
        if self.has_account:
            self.msg("|gYou feel rejuvenated and ready to fight again!|n")

    def sync_hp(self):
        """保持 hp 与 HP 字段同步。"""
        if hasattr(self.db, "hp"):
            self.db.HP = self.db.hp
        if hasattr(self.db, "HP"):
            self.db.hp = self.db.HP

    # ------------------------------------------------------------------
    # 移动前置钩子：阻止战斗中或被击败角色移动
    # ------------------------------------------------------------------
    def at_pre_move(self, destination, move_type="move", **kwargs):
        # HP 字段同步
        self.sync_hp()

        if self.db.state == STATE_DEFEATED:
            self.msg("You are defeated and cannot move!")
            return False
        if self.rules.is_in_combat(self):
            self.msg("You can't leave while in combat!")
            return False
        return True

    # ------------------------------------------------------------------
    # 外观描述：包括穿着信息
    # ------------------------------------------------------------------
    def get_display_desc(self, looker, **kwargs):
        """返回角色描述并追加服装信息。"""
        desc = self.db.desc or f"你看到了 {self.get_display_name(looker)}。"

        # 生成服装描述
        outfit_list = []
        for garment in get_worn_clothes(self, exclude_covered=True):
            wearstyle = garment.db.worn
            if isinstance(wearstyle, str):
                outfit_list.append(f"{garment.name} {wearstyle}")
            else:
                outfit_list.append(garment.name)

        if outfit_list:
            outfit = f"{self.get_display_name(looker, **kwargs)} 穿着 {iter_to_str(outfit_list)}。"
        else:
            outfit = f"{self.get_display_name(looker, **kwargs)} 没有穿任何衣物。"

        return f"{desc}\n\n{outfit}" if desc else outfit

    # ------------------------------------------------------------------
    # NPC 战斗 AI
    # ------------------------------------------------------------------
    def ai_combat_action(self):
        """仅在 NPC 回合时由 `CombatAIScript` 调用。"""
        if self.db.state != STATE_ALIVE:
            return

        # 仅非玩家角色执行
        if not self.has_account and self.rules.is_turn(self):
            turnhandler = self.db.combat_turnhandler
            if not turnhandler:
                return

            # 获取可攻击敌人
            enemies = [f for f in turnhandler.db.fighters if f is not self and f.db.hp > 0]
            if not enemies:
                self.execute_cmd("disengage")
                return

            # 根据概率选择行动
            rand = random.random()
            if rand < self.combat_probabilities["attack"]:
                target = random.choice(enemies)
                self.execute_cmd(f"attack {target.key}")
            elif rand < self.combat_probabilities["attack"] + self.combat_probabilities["pass"]:
                self.execute_cmd("pass")
            else:
                self.execute_cmd("disengage")

    # ---------------------------------------------------------------------
    # 状态显示方法
    # ---------------------------------------------------------------------
    def get_status_display(self, for_combat=False):
        """
        生成角色状态的 rich 格式显示
        
        Args:
            for_combat (bool): 是否为战斗中的状态显示
            
        Returns:
            str: 格式化后的状态显示文本
        """
        console = Console(width=70, force_terminal=True, emoji=True)

        # ── 魔幻主题表格 ────────────────────────────────────────────────────
        status_table = Table(
            show_header=True,
            header_style="bold magenta underline",
            box=box.ROUNDED,                 # 圆角边框
            row_styles=["", "dim"],          # 交替行色
            pad_edge=False,
            expand=True,
        )
        status_table.add_column("✨ 属性", style="bright_cyan", min_width=14)
        status_table.add_column("🔮 数值", style="bright_green", min_width=10, justify="right")
        status_table.add_column("📜 说明", style="bright_yellow", min_width=22)

        # ── 基础信息 ───────────────────────────────────────────────────────
        status_table.add_row("姓名", self.key, f"状态: {getattr(self.db, 'state', '未知')}")

        # ── 生命值（带彩色血条） ───────────────────────────────────────────
        hp_current = getattr(self.db, "hp", 0)
        hp_max = getattr(self.db, "max_hp", 100) or 1
        hp_percent = hp_current / hp_max

        # 颜色梯度根据血量百分比变换
        if hp_percent > 0.75:
            hp_style = "bold bright_green"
        elif hp_percent > 0.5:
            hp_style = "bold yellow"
        elif hp_percent > 0.25:
            hp_style = "bold orange1"
        else:
            hp_style = "bold bright_red"

        # 渐变血条：前景 █、背景 ░
        bar_len = 22
        filled_len = int(bar_len * hp_percent)
        bar = f"[red]{'█' * filled_len}[/red][grey35]{'░' * (bar_len - filled_len)}[/grey35]"
        hp_display = Text.assemble("♥ ", (f"{hp_current}/{hp_max}", hp_style))

        status_table.add_row("生命值", hp_display, bar)

        # ── Traits 属性 ───────────────────────────────────────────────────
        if hasattr(self, "traits"):
            try:
                strength = self.traits.strength
                dexterity = self.traits.dexterity
                constitution = self.traits.constitution

                status_table.add_row("💪 力量", f"{strength.value}", f"基础: {strength.base}")
                status_table.add_row("🤸 敏捷", f"{dexterity.value}", f"基础: {dexterity.base}")
                status_table.add_row("🛡️ 体质", f"{constitution.value}", f"基础: {constitution.base}")
            except AttributeError:
                status_table.add_row("属性", "未初始化", "请使用 rest 命令重新设置")

        # ── 战斗信息 ───────────────────────────────────────────────────────
        if for_combat and self.rules.is_in_combat(self):
            turnhandler = getattr(self.db, "combat_turnhandler", None)
            if turnhandler:
                is_turn = self.rules.is_turn(self)
                actions_left = getattr(self.db, "combat_actionsleft", 0)
                last_action = getattr(self.db, "combat_lastaction", "none")

                status_table.add_row("⚔️ 当前回合", "是" if is_turn else "否", "")
                status_table.add_row("🔁 剩余行动", str(actions_left), "")
                status_table.add_row("🗡️ 上次行动", last_action, "")

        # ── 其他状态 ───────────────────────────────────────────────────────
        if hasattr(self.db, "death_count"):
            status_table.add_row("💀 死亡次数", str(self.db.death_count), "")

        # ── 魔幻面板包装 ───────────────────────────────────────────────────
        title_icon = "⚔️" if for_combat else "📊"
        panel = Panel(
            Align.center(status_table),
            title=f"{title_icon} {self.key} 的属性状态",
            border_style="bright_magenta",
            padding=(1, 2),
        )

        # ── 渲染为字符串返回 ────────────────────────────────────────────────
        with console.capture() as capture:
            console.print(panel)

        return capture.get()


# ---------------------------------------------------------------------------
# 自定义 TurnHandler：支持战斗豁免
# ---------------------------------------------------------------------------
class CombinedTurnHandler(TBBasicTurnHandler):
    """扩展基础回合处理：过滤 immune 角色。"""

    rules = COMBINED_RULES

    def at_script_creation(self):
        """初始化战斗并过滤免疫者。"""
        self.key = "Combat Turn Handler"
        self.interval = 5  # 每 5 秒驱动一次
        self.persistent = True
        self.db.fighters = []

        # 首轮收集拥有生命值的对象
        for thing in self.obj.contents:
            if thing.db.hp:
                self.db.fighters.append(thing)

        # 过滤免疫角色
        immune_fighters = []
        for fighter in self.db.fighters[:]:
            if getattr(fighter.db, "immune_combat", False):
                immune_fighters.append(fighter)
                self.db.fighters.remove(fighter)
                self.rules.combat_cleanup(fighter)

        if immune_fighters:
            names = ", ".join(f.key for f in immune_fighters)
            self.obj.msg_contents(f"{names} cannot be drawn into combat.")

        # 初始化战斗信息
        for fighter in self.db.fighters:
            self.initialize_for_combat(fighter)

        # 向房间保存引用
        self.obj.db.combat_turnhandler = self

        # 投掷先攻并排序
        self.db.fighters = sorted(self.db.fighters, key=self.rules.roll_init, reverse=True)
        self.obj.msg_contents("Turn order is: %s " % ", ".join(o.key for o in self.db.fighters))

        # 开始首个角色回合
        self.start_turn(self.db.fighters[0])

        # 记录当前回合与计时器
        self.db.turn = 0
        self.db.timer = TURN_TIMEOUT

    def start_turn(self, character):
        """
        重写 start_turn 方法，在开始回合时显示角色状态
        
        Args:
            character: 开始回合的角色
        """
        # 调用父类方法设置回合
        super().start_turn(character)
        
        # 显示角色状态（如果角色支持状态显示）
        if hasattr(character, 'get_status_display'):
            status_display = character.get_status_display(for_combat=True)
            self.obj.msg_contents(f"\n{status_display}")
        else:
            # 备用简单显示
            self.obj.msg_contents(f"|c{character.key} 的回合开始！生命值: {character.db.hp}/{character.db.max_hp}|n")

    # ------------------------------------------------------------------
    # 动态加入战斗
    # ------------------------------------------------------------------
    def join_fight(self, character):
        if getattr(character.db, "immune_combat", False):
            character.msg("You are immune to being drawn into combat.")
            self.obj.msg_contents(f"{character.key} cannot be drawn into combat.")
            return
        super().join_fight(character)


# ---------------------------------------------------------------------------
# 命令包装：绑定自定义规则
# ---------------------------------------------------------------------------
class CmdStatus(Command):
    """
    显示角色的详细状态信息
    
    Usage:
      status
      
    显示你的生命值、属性、战斗状态等信息，使用精美的表格格式。
    """
    
    key = "status"
    aliases = ["stat", "stats"]
    locks = "cmd:all()"
    help_category = "general"
    
    def func(self):
        """执行状态显示命令"""
        if not hasattr(self.caller, 'get_status_display'):
            self.caller.msg("状态显示功能不可用。")
            return
            
        # 检查是否在战斗中
        in_combat = hasattr(self.caller, 'rules') and self.caller.rules.is_in_combat(self.caller)
        
        # 获取并显示状态
        status_display = self.caller.get_status_display(for_combat=in_combat)
        self.caller.msg(status_display)


class CmdAttackNew(CmdAttack):
    rules = COMBINED_RULES


class CmdPassNew(CmdPass):
    rules = COMBINED_RULES


class CmdDisengageNew(CmdDisengage):
    rules = COMBINED_RULES


class CmdRestNew(CmdRest):
    rules = COMBINED_RULES


class CmdCombatHelpNew(CmdCombatHelp):
    rules = COMBINED_RULES


class CmdRAG(Command):
    """
    RAG系统管理命令
    
    Usage:
      rag
      rag status
      rag add <knowledge>
      rag reindex [--force]
      
    管理RAG（检索增强生成）系统，用于增强战斗叙述的上下文。
    
    Examples:
      rag status          - 查看RAG系统状态
      rag add 飞剑术：以剑气御敌的远程攻击 - 添加武侠知识
      rag reindex         - 增量重新索引（只处理新增或修改的文档）
      rag reindex --force - 强制重新索引所有文档
    """
    
    key = "rag"
    aliases = ["知识库", "kb"]
    locks = "cmd:all()"
    help_category = "system"
    
    def func(self):
        """执行RAG管理命令"""
        if not self.args:
            self.args = "status"
            
        args = self.args.strip().split(" ", 1)
        cmd = args[0].lower()
        
        if cmd == "status":
            self._show_status()
        elif cmd == "add" and len(args) > 1:
            self._add_knowledge(args[1])
        elif cmd == "reindex":
            # 检查是否有 --force 参数
            force_reindex = len(args) > 1 and args[1].strip().lower() == "--force"
            self._reindex_documents(force_reindex)
        else:
            self.caller.msg(self.__doc__)
    
    def _show_status(self):
        """显示RAG系统状态"""
        try:
            rag = get_rag_manager()
            stats = rag.get_stats()
            
            status_msg = []
            status_msg.append("|c=== RAG系统状态 ===|n")
            status_msg.append(f"系统可用性: {'|g可用|n' if stats.get('rag_available') else '|r不可用（缺少依赖）|n'}")
            
            if stats.get('rag_available'):
                status_msg.append(f"文档文件数: |y{stats.get('total_files', 0)}|n")
                status_msg.append(f"文档块总数: |y{stats.get('total_documents', 0)}|n")
                status_msg.append(f"集合名称: |c{stats.get('collection_name', 'N/A')}|n")
                status_msg.append(f"嵌入模型: |m{stats.get('embedding_model', 'N/A')}|n")
                status_msg.append(f"缓存大小: |w{stats.get('cache_size', 0)}|n")
                
                config = stats.get('config', {})
                if config:
                    status_msg.append("")
                    status_msg.append("|c=== 配置信息 ===|n")
                    status_msg.append(f"文档路径: {config.get('documents_path', 'N/A')}")
                    status_msg.append(f"数据库路径: {config.get('vector_db_path', 'N/A')}")
                    status_msg.append(f"相似度阈值: {config.get('similarity_threshold', 0.7)}")
                    status_msg.append(f"最大结果数: {config.get('max_results', 5)}")
            else:
                status_msg.append("")
                status_msg.append("|r要启用RAG系统，请安装依赖：|n")
                status_msg.append("|wpip install weaviate-client langchain-community|n")
                status_msg.append("|r并确保Weaviate服务器正在运行|n")
            
            self.caller.msg("\n".join(status_msg))
            
        except Exception as e:
            self.caller.msg(f"|r获取RAG状态失败: {e}|n")
    
    def _add_knowledge(self, knowledge: str):
        """添加知识到RAG系统"""
        try:
            success = add_battle_knowledge(knowledge, f"player_{self.caller.key}")
            if success:
                self.caller.msg(f"|g成功添加知识：{knowledge[:50]}{'...' if len(knowledge) > 50 else ''}|n")
            else:
                self.caller.msg("|r添加知识失败，请检查RAG系统状态|n")
        except Exception as e:
            self.caller.msg(f"|r添加知识失败: {e}|n")
    
    def _reindex_documents(self, force_reindex: bool = False):
        """重新索引文档"""
        try:
            rag = get_rag_manager()
            
            if force_reindex:
                self.caller.msg("|y开始强制重新索引所有文档...|n")
            else:
                self.caller.msg("|y开始增量索引检查...|n")
            
            count = rag.index_documents(force_reindex=force_reindex)
            
            if count > 0:
                mode = "强制重新索引" if force_reindex else "增量索引"
                self.caller.msg(f"|g{mode}完成，处理了 {count} 个文档块|n")
            else:
                if force_reindex:
                    self.caller.msg("|y强制重新索引完成，但未找到任何文档|n")
                else:
                    self.caller.msg("|y增量索引完成，没有需要更新的文档|n")
        except Exception as e:
            self.caller.msg(f"|r重新索引失败: {e}|n")


# ---------------------------------------------------------------------------
# 角色 CmdSet：整合战斗与服装命令
# ---------------------------------------------------------------------------
class CombinedCharacterCmdSet(default_cmds.CharacterCmdSet):
    """角色默认 CmdSet：包含自定义战斗命令和服装系统。"""

    key = "DefaultCharacter"

    def at_cmdset_creation(self):
        super().at_cmdset_creation()

        # ---- 通用命令 ----
        self.add(CmdStatus())
        self.add(CmdRAG())

        # ---- 战斗命令 ----
        class CmdFightImproved(CmdFight):
            rules = COMBINED_RULES
            combat_handler_class = CombinedTurnHandler

        self.add(CmdFightImproved())
        self.add(CmdAttackNew())
        self.add(CmdPassNew())
        self.add(CmdDisengageNew())
        self.add(CmdRestNew())
        self.add(CmdCombatHelpNew())
        
        # ---- 装备命令 ----
        self.add(CmdEquip())
        self.add(CmdUnequip())

        # ---- 服装系统命令 ----
        from evennia.contrib.game_systems.clothing.clothing import (
            CmdWear,
            CmdRemove,
            CmdCover,
            CmdUncover,
            CmdInventory,
        )

        self.add(CmdWear())
        self.add(CmdRemove())
        self.add(CmdCover())
        self.add(CmdUncover())
        self.add(CmdInventory())