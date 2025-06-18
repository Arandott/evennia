#!/usr/bin/env python3
"""
最小测试脚本：traits + clothing + turnbattle.tb_basic

这个脚本创建了一个集成了三个contrib系统的测试环境：
1. traits - 角色特征系统
2. clothing - 服装系统  
3. turnbattle.tb_basic - 基础回合制战斗

使用方法：
1. 启动evennia服务器
2. 运行此脚本: python test_minimal_game.py
3. 进入游戏测试各种功能

注意：这个脚本解决了clothing和turnbattle的Character类继承冲突
"""

import os
import django
from collections import defaultdict

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server.conf.settings')
django.setup()

from evennia import create_object, DefaultRoom, DefaultCharacter, default_cmds
from evennia.utils import lazy_property, iter_to_str, group_objects_by_key_and_desc, crop
from evennia.utils.ansi import raw as raw_ansi

# 导入contrib系统
from evennia.contrib.rpg.traits import TraitHandler
from evennia.contrib.game_systems.clothing.clothing import (
    ContribClothing, get_worn_clothes, order_clothes_list, 
    ClothedCharacterCmdSet, CLOTHING_OVERALL_LIMIT, CLOTHING_TYPE_LIMIT,
    single_type_count, WEARSTYLE_MAXLENGTH
)
from evennia.contrib.game_systems.turnbattle.tb_basic import (
    TBBasicCharacter, BattleCmdSet, COMBAT_RULES
)


class CombinedCharacter(TBBasicCharacter):
    """
    组合Character类：继承TBBasicCharacter，集成clothing和traits功能
    
    优先保证战斗系统完整性，手动集成服装显示功能
    """
    
    rules = COMBAT_RULES
    
    @lazy_property
    def traits(self):
        """添加traits支持"""
        return TraitHandler(self)
    
    def at_object_creation(self):
        """角色创建时初始化"""
        super().at_object_creation()
        
        # 添加一些基础特征
        self.traits.add("strength", "力量", trait_type="static", base=10, mod=0)
        self.traits.add("dexterity", "敏捷", trait_type="static", base=10, mod=0)
        self.traits.add("constitution", "体质", trait_type="static", base=10, mod=0)
        self.traits.add("hp", "生命值", trait_type="gauge", base=self.db.max_hp, min=0)
        
        # 同步HP值
        self.traits.hp.current = self.db.hp
        
    def get_display_desc(self, looker, **kwargs):
        """
        集成clothing系统的外观显示功能
        重写此方法以显示穿着的服装
        """
        desc = self.db.desc

        outfit_list = []
        # 添加穿着的、未被覆盖的服装到描述中
        for garment in get_worn_clothes(self, exclude_covered=True):
            wearstyle = garment.db.worn
            if type(wearstyle) is str:
                outfit_list.append(f"{garment.name} {wearstyle}")
            else:
                outfit_list.append(garment.name)

        # 创建服装描述字符串
        if outfit_list:
            outfit = (
                f"{self.get_display_name(looker, **kwargs)} is wearing {iter_to_str(outfit_list)}."
            )
        else:
            outfit = f"{self.get_display_name(looker, **kwargs)} is wearing nothing."

        # 添加到基础描述
        if desc:
            desc += f"\n\n{outfit}"
        else:
            desc = outfit

        return desc

    def get_display_things(self, looker, **kwargs):
        """
        集成clothing系统的物品显示功能
        重写此方法以正确显示携带的物品（排除已穿着的）
        """
        def _filter_visible(obj_list):
            return (
                obj
                for obj in obj_list
                if obj != looker and obj.access(looker, "view") and not obj.db.worn
            )

        # 获取可见物品（排除穿着的）
        things = _filter_visible(self.contents_get(content_type="object"))

        grouped_things = defaultdict(list)
        for thing in things:
            grouped_things[thing.get_display_name(looker, **kwargs)].append(thing)

        thing_names = []
        for thingname, thinglist in sorted(grouped_things.items()):
            nthings = len(thinglist)
            thing = thinglist[0]
            singular, plural = thing.get_numbered_name(nthings, looker, key=thingname)
            thing_names.append(singular if nthings == 1 else plural)
        thing_names = iter_to_str(thing_names)
        return (
            f"\n{self.get_display_name(looker, **kwargs)} is carrying {thing_names}"
            if thing_names
            else ""
        )


class CombinedCharacterCmdSet(default_cmds.CharacterCmdSet):
    """
    组合命令集：集成战斗和服装命令
    """
    
    key = "DefaultCharacter"

    def at_cmdset_creation(self):
        """创建命令集"""
        super().at_cmdset_creation()
        
        # 添加战斗系统命令
        from evennia.contrib.game_systems.turnbattle.tb_basic import (
            CmdFight, CmdAttack, CmdPass, CmdDisengage, CmdRest, CmdCombatHelp
        )
        self.add(CmdFight())
        self.add(CmdAttack())
        self.add(CmdPass())
        self.add(CmdDisengage())
        self.add(CmdRest())
        self.add(CmdCombatHelp())
        
        # 添加服装系统命令
        from evennia.contrib.game_systems.clothing.clothing import (
            CmdWear, CmdRemove, CmdCover, CmdUncover, CmdInventory
        )
        self.add(CmdWear())
        self.add(CmdRemove())
        self.add(CmdCover())
        self.add(CmdUncover())
        self.add(CmdInventory())


def create_test_room():
    """创建测试房间和角色"""
    
    print("正在创建测试环境...")
    
    # 创建测试房间
    test_room = create_object(
        DefaultRoom,
        key="测试竞技场",
        aliases=["arena", "test"],
    )
    test_room.db.desc = (
        "这是一个专门用于测试战斗、服装和特征系统的竞技场。"
        "\n你可以在这里测试各种功能：战斗、穿装备、查看属性等。"
        "\n\n可用命令："
        "\n|w战斗系统:|n fight, attack <目标>, pass, disengage, rest"
        "\n|w服装系统:|n wear <物品>, remove <物品>, cover <物品1> with <物品2>, inventory"
        "\n|w特征系统:|n 通过Python代码访问 self.traits.属性名"
    )
    
    # 创建测试角色1
    char1 = create_object(
        CombinedCharacter,
        key="测试战士",
        aliases=["warrior", "char1"],
        location=test_room
    )
    char1.db.desc = "一个勇敢的测试战士"
    
    # 创建测试角色2 
    char2 = create_object(
        CombinedCharacter,
        key="测试法师",
        aliases=["mage", "char2"], 
        location=test_room
    )
    char2.db.desc = "一个聪明的测试法师"
    
    # 为角色2设置不同的属性
    char2.traits.strength.base = 8
    char2.traits.dexterity.base = 12
    char2.traits.constitution.base = 9
    
    # 创建一些测试服装
    shirt = create_object(
        ContribClothing,
        key="测试衬衫",
        aliases=["shirt"],
        location=char1
    )
    shirt.db.desc = "一件简单的测试衬衫"
    shirt.db.clothing_type = "top"
    
    pants = create_object(
        ContribClothing,
        key="测试裤子", 
        aliases=["pants"],
        location=char1
    )
    pants.db.desc = "一条舒适的测试裤子"
    pants.db.clothing_type = "bottom"
    
    hat = create_object(
        ContribClothing,
        key="测试帽子",
        aliases=["hat"],
        location=char2
    )
    hat.db.desc = "一顶时髦的测试帽子"
    hat.db.clothing_type = "hat"
    
    robe = create_object(
        ContribClothing,
        key="法师长袍",
        aliases=["robe"],
        location=char2
    )
    robe.db.desc = "一件神秘的法师长袍"
    robe.db.clothing_type = "fullbody"
    
    print(f"✅ 测试房间创建完成: {test_room.key} (#{test_room.id})")
    print(f"✅ 角色创建完成: {char1.key} (#{char1.id}), {char2.key} (#{char2.id})")
    print(f"✅ 服装创建完成: 衬衫、裤子、帽子、长袍")
    
    # 显示测试说明
    print("\n" + "="*50)
    print("🎮 测试环境设置完成！")
    print("="*50)
    print(f"房间ID: #{test_room.id}")
    print(f"角色ID: #{char1.id}, #{char2.id}")
    print("\n📝 测试建议:")
    print("1. 进入游戏后使用 @tel #{} 传送到测试房间".format(test_room.id))
    print("2. 使用 @ic #{} 控制测试角色".format(char1.id))
    print("3. 测试命令:")
    print("   - look 查看房间和角色描述")
    print("   - wear shirt 穿上衬衫")
    print("   - inventory 查看物品清单")
    print("   - fight 开始战斗")
    print("   - attack <目标> 攻击其他角色")
    print("4. 特征系统通过Python代码测试:")
    print("   - 在游戏中使用 @py self.traits.strength.value")
    print("   - 或者 @py self.traits.hp.current")
    
    return test_room, char1, char2


def test_functionality():
    """测试各系统功能"""
    print("\n🔧 运行功能测试...")
    
    room, char1, char2 = create_test_room()
    
    # 测试traits
    print(f"🔹 traits测试: {char1.key}的力量值: {char1.traits.strength.value}")
    print(f"🔹 traits测试: {char2.key}的敏捷值: {char2.traits.dexterity.value}")
    
    # 测试clothing
    shirt = char1.search("shirt", quiet=True)
    if shirt:
        print(f"🔹 clothing测试: 找到服装 {shirt.key}")
    
    # 测试combat
    print(f"🔹 combat测试: {char1.key}的HP: {char1.db.hp}")
    print(f"🔹 combat测试: 战斗规则: {char1.rules}")
    
    print("✅ 所有系统初始化正常！")


if __name__ == "__main__":
    print("🚀 启动最小测试环境...")
    print("集成系统: traits + clothing + turnbattle.tb_basic")
    print("解决方案: 继承TBBasicCharacter + 手动集成clothing功能")
    
    test_functionality()
    
    print("\n🎯 下一步:")
    print("1. 启动Evennia服务器: evennia start")
    print("2. 连接游戏进行测试")
    print("3. 检查各系统是否正常工作") 