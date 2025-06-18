from evennia.objects.objects import DefaultObject
from evennia import Command
from evennia.utils import logger

# ---------------------------------------------------------------------------
# 武器系统常量
# ---------------------------------------------------------------------------
WEAPON_TYPES = {
    "sword": {"name": "剑", "damage_bonus": 1.2, "hit_bonus": 0.1},
    "spear": {"name": "枪", "damage_bonus": 1.1, "hit_bonus": 0.15},
    "axe": {"name": "斧", "damage_bonus": 1.3, "hit_bonus": 0.05},
    "bow": {"name": "弓", "damage_bonus": 1.0, "hit_bonus": 0.2},
    "staff": {"name": "法杖", "damage_bonus": 0.8, "hit_bonus": 0.1},
}


# ---------------------------------------------------------------------------
# 武器类
# ---------------------------------------------------------------------------
class Weapon(DefaultObject):
    """武器对象类"""
    
    def at_object_creation(self):
        """武器创建时初始化属性"""
        super().at_object_creation()
        
        # 武器基础属性
        self.db.weapon_type = "sword"  # 武器类型
        self.db.damage_min = 10        # 最小伤害
        self.db.damage_max = 20        # 最大伤害
        self.db.accuracy = 0.8         # 命中率加成
        self.db.critical_rate = 0.05   # 暴击率
        self.db.durability = 100       # 耐久度
        self.db.max_durability = 100   # 最大耐久度
        self.db.quality = "common"     # 品质: common, rare, epic, legendary
        self.db.required_level = 1     # 需求等级
        self.db.required_stats = {}    # 需求属性 {"strength": 10}
        
        # 特殊属性
        self.db.enchantments = []      # 附魔效果
        self.db.set_bonus = None       # 套装效果
        
    def get_damage_range(self):
        """获取武器伤害范围"""
        weapon_data = WEAPON_TYPES.get(self.db.weapon_type, WEAPON_TYPES["sword"])
        multiplier = weapon_data["damage_bonus"]
        
        min_dmg = int(self.db.damage_min * multiplier)
        max_dmg = int(self.db.damage_max * multiplier)
        
        return min_dmg, max_dmg
    
    def get_display_name(self, looker=None, **kwargs):
        """显示武器名称，包含品质颜色"""
        quality_colors = {
            "common": "|w",    # 白色
            "rare": "|b",      # 蓝色  
            "epic": "|m",      # 紫色
            "legendary": "|y"  # 黄色
        }
        
        color = quality_colors.get(self.db.quality, "|w")
        durability_pct = self.db.durability / self.db.max_durability
        
        condition = ""
        if durability_pct < 0.3:
            condition = "|r[破损]|n"
        elif durability_pct < 0.6:
            condition = "|y[磨损]|n"
            
        return f"{color}{self.key}|n{condition}"
    
    
# ---------------------------------------------------------------------------
# 装备管理器
# ---------------------------------------------------------------------------
class EquipmentHandler:
    """装备管理器"""
    
    def __init__(self, character):
        self.character = character
        self._load_equipment()
    
    def _load_equipment(self):
        """加载装备数据"""
        logger.log_info(f"加载装备数据: {self.character.db.equipped}")
        if self.character.db.equipped is None:
            self.character.db.equipped = {
                "weapon": None,      # 武器
                "armor": None,       # 护甲
                "helmet": None,      # 头盔
                "boots": None,       # 靴子
                "accessory": None,   # 饰品
            }
            logger.log_info(f"成功加载装备数据: {self.character.db.equipped}")
    
    def equip_weapon(self, weapon):
        """装备武器"""
        if not isinstance(weapon, Weapon):
            return False, "不是有效的武器"
        
        # ✅ 检查武器是否在角色身上
        if weapon.location != self.character:
            return False, "你必须先拿到这件武器才能装备它"
        
        # 检查需求
        if not self._check_requirements(weapon):
            return False, "不满足装备需求"
        
        # 卸下旧武器
        old_weapon = self.character.db.equipped["weapon"]
        if old_weapon:
            old_weapon.location = self.character
            self.character.location.msg_contents(f"{self.character.key} 卸下了 {old_weapon.key}")
        
        # 装备新武器
        self.character.db.equipped["weapon"] = weapon
        weapon.location = self.character  # 移动到角色身上
        
        self.character.location.msg_contents(f"{self.character.key} 装备了 {weapon.get_display_name()}")
        return True, f"装备了{weapon.key}"
    
    def unequip_weapon(self):
        """卸下武器"""
        weapon = self.character.db.equipped["weapon"]
        if not weapon:
            return False, "没有装备武器"
        
        self.character.db.equipped["weapon"] = None
        self.character.location.msg_contents(f"{self.character.key} 卸下了 {weapon.key}")
        return True, f"卸下了{weapon.key}"
    
    def get_weapon(self):
        """获取当前装备的武器"""
        return self.character.db.equipped.get("weapon")
    
    def _check_requirements(self, item):
        """检查装备需求"""
        if hasattr(item.db, 'required_stats'):
            for stat, required_value in item.db.required_stats.items():
                if hasattr(self.character.traits, stat):
                    if getattr(self.character.traits, stat).value < required_value:
                        return False
        return True
    
    def get_total_stats(self):
        """获取装备提供的总属性加成"""
        stats = {"damage_bonus": 0, "accuracy_bonus": 0, "defense_bonus": 0}
        
        weapon = self.get_weapon()
        if weapon:
            weapon_data = WEAPON_TYPES.get(weapon.db.weapon_type, WEAPON_TYPES["sword"])
            stats["damage_bonus"] += weapon_data["damage_bonus"] - 1.0  # 减去基础1.0
            stats["accuracy_bonus"] += weapon_data["hit_bonus"]
        
        return stats
    
    
# ---------------------------------------------------------------------------
# 武器和技能命令
# ---------------------------------------------------------------------------
class CmdEquip(Command):
    """
    装备武器或防具
    
    Usage:
      equip <item>
      wield <item>
    
    装备指定的武器或防具。
    """
    
    key = "equip"
    aliases = ["wield", "wear_weapon"]
    locks = "cmd:all()"
    help_category = "equipment"
    
    def func(self):
        if not self.args:
            self.caller.msg("装备什么？")
            return
        
        # ✅ 只在角色身上搜索，不搜索房间
        item = self.caller.search(self.args, location=self.caller, quiet=True)
        
        if not item:
            # 如果在身上找不到，检查是否在房间里
            room_item = self.caller.search(self.args, location=self.caller.location, quiet=True)
            if room_item:
                room_item = room_item[0]
                self.caller.msg(f"你需要先拿起 {room_item.key}。使用 'get {room_item.key}' 命令。")
            else:
                self.caller.msg(f"你身上没有 '{self.args}'。")
            return
        
        item = item[0]
        if isinstance(item, Weapon):
            success, msg = self.caller.equipment.equip_weapon(item)
            self.caller.msg(msg)
        else:
            self.caller.msg(f"物品类型: {item.__class__.__name__}")
            self.caller.msg("这不是可装备的物品。")

class CmdUnequip(Command):
    """
    卸下装备
    
    Usage:
      unequip weapon
      unwield
    """
    
    key = "unequip"
    aliases = ["unwield", "remove_weapon"]
    locks = "cmd:all()"
    help_category = "equipment"
    
    def func(self):
        if not self.args or self.args.lower() in ["weapon", "武器"]:
            success, msg = self.caller.equipment.unequip_weapon()
            self.caller.msg(msg)
        else:
            self.caller.msg("卸下什么装备？")