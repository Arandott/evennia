# Contrib 系统集成说明

本文档记录了如何在 my_first_game 中集成 traits + clothing + turnbattle.tb_basic 系统。

## ✅ 已完成的修改

### 1. 角色类 (typeclasses/characters.py)
- 修改 `Character` 类继承自 `CombinedCharacter`
- 集成了战斗、服装和特征系统

### 2. 命令集 (commands/default_cmdsets.py)  
- 修改 `CharacterCmdSet` 继承自 `CombinedCharacterCmdSet`
- 自动包含所有战斗和服装命令

### 3. 集成类 (typeclasses/integrated_character.py)
- 创建了解决冲突的 `CombinedCharacter` 类
- 优先保证 turnbattle 系统完整性
- 手动集成 clothing 显示功能
- 通过 @lazy_property 添加 traits 支持

### 4. 测试环境 (world/minimal_test.ev)
- 批处理脚本，创建完整测试环境
- 包含测试房间、角色、服装物品

## 🎮 可用功能

### 战斗系统
```
fight           - 开始战斗
attack <目标>   - 攻击其他角色
pass           - 跳过回合
disengage      - 结束战斗
rest           - 恢复生命值
help combat    - 查看战斗帮助
```

### 服装系统
```
wear <物品>               - 穿戴服装
remove <物品>             - 脱下服装  
cover <物品1> with <物品2> - 用一件服装覆盖另一件
uncover <物品>            - 显示被覆盖的服装
inventory                - 查看物品清单（区分穿戴/携带）
```

### 特征系统
```
@py self.traits.strength.value     - 查看力量值
@py self.traits.dexterity.value    - 查看敏捷值
@py self.traits.constitution.value - 查看体质值
@py self.traits.hp.current         - 查看当前生命值
@py self.traits.hp.max            - 查看最大生命值

# 修改属性示例
@py self.traits.strength.base = 15
@py self.traits.hp.current -= 10
```

## 🚀 快速开始

### 1. 启动服务器
```bash
evennia start
```

### 2. 连接游戏
在游戏中进入 Limbo (#2)

### 3. 加载测试环境
```
batchcommand world.minimal_test
```

### 4. 进入测试区域
```
arena
```

### 5. 查看测试说明
```
look sign
```

## 🧪 测试建议

### 基础测试
1. `look warrior` - 查看角色（会显示穿着的服装）
2. `look mage` - 查看法师
3. `inventory` - 查看物品清单

### 服装测试
1. `wear shirt` - 穿上衬衫
2. `look self` - 查看自己的外观变化
3. `remove shirt` - 脱下衬衫
4. `wear hat` - 测试不同类型服装
5. `wear spare_hat` - 测试服装数量限制（帽子只能戴一个）

### 战斗测试
1. `fight` - 开始战斗
2. `attack warrior` - 攻击战士
3. `pass` - 跳过回合
4. `disengage` - 结束战斗
5. `rest` - 恢复生命值

### 特征测试
1. `@py self.traits.strength.value` - 查看力量值
2. `@py self.traits.hp.current` - 查看当前HP
3. `@py self.traits.strength.base = 15` - 修改力量值
4. `@py self.traits.hp.current -= 10` - 减少HP

## 🔧 技术细节

### 冲突解决方案
- **问题**: clothing 和 turnbattle 都需要不同的 Character 继承
- **解决**: 继承 `TBBasicCharacter`，手动集成 `ClothedCharacter` 功能

### 核心集成类
```python
class CombinedCharacter(TBBasicCharacter):
    @lazy_property
    def traits(self):
        return TraitHandler(self)
        
    def get_display_desc(self, looker, **kwargs):
        # 集成服装显示功能
```

### 自动初始化特征
每个新角色自动获得：
- strength (力量): 10
- dexterity (敏捷): 10  
- constitution (体质): 10
- hp (生命值): 100 (仪表类型，与战斗系统同步)

## 📝 自定义扩展

### 添加新特征
```python
# 在角色创建时添加
self.traits.add("intelligence", "智力", trait_type="static", base=10)
self.traits.add("mana", "法力值", trait_type="gauge", base=50, min=0)
```

### 修改服装限制
在 settings.py 中添加：
```python
CLOTHING_TYPE_LIMIT = {
    "hat": 1, 
    "gloves": 1, 
    "shoes": 1,
    "ring": 2  # 允许戴两个戒指
}
```

### 添加自定义命令
在 `CharacterCmdSet.at_cmdset_creation()` 中：
```python
self.add(YourCustomCommand())
```

## ⚠️ 注意事项

1. **服装限制**: 帽子、手套、鞋子默认只能穿一个
2. **战斗要求**: 需要在有其他角色的房间中才能开始战斗
3. **特征同步**: HP 特征与战斗系统的 HP 保持同步
4. **命令优先级**: 集成的命令会覆盖默认命令（如 inventory）

## 🐛 故障排除

### 如果命令不工作
1. 确认已重启服务器：`evennia reload`
2. 检查是否有语法错误：查看服务器日志
3. 确认角色类型：`@py type(self)`

### 如果特征不存在
```python
# 手动添加特征
@py self.traits.add("strength", "力量", trait_type="static", base=10)
```

### 如果服装不显示
1. 确认服装类型：`@py shirt.db.clothing_type`
2. 确认穿戴状态：`@py shirt.db.worn`

## 📚 相关文档

- [Traits System](evennia/contrib/rpg/traits/README.md)
- [Clothing System](evennia/contrib/game_systems/clothing/README.md)  
- [Turn Battle System](evennia/contrib/game_systems/turnbattle/README.md) 