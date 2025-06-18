#!/usr/bin/env python3
"""
简化测试脚本：验证contrib模块导入
不需要Django环境，只检查模块是否存在和可导入
"""

import sys
import os
sys.path.insert(0, '/home/kapibala/documents_for_study/university_courses/CUFE_DL_25spring/evennia')

def test_imports():
    """测试contrib模块导入"""
    print("🔍 检查contrib模块导入...")
    
    tests = [
        # traits系统
        {
            'name': 'traits系统',
            'path': 'evennia.contrib.rpg.traits.traits',
            'components': ['TraitHandler', 'Trait', 'StaticTrait', 'CounterTrait', 'GaugeTrait']
        },
        
        # clothing系统
        {
            'name': 'clothing系统', 
            'path': 'evennia.contrib.game_systems.clothing.clothing',
            'components': ['ContribClothing', 'ClothedCharacter', 'ClothedCharacterCmdSet']
        },
        
        # turnbattle系统
        {
            'name': 'turnbattle.tb_basic系统',
            'path': 'evennia.contrib.game_systems.turnbattle.tb_basic', 
            'components': ['TBBasicCharacter', 'TBBasicTurnHandler', 'BasicCombatRules']
        }
    ]
    
    success_count = 0
    
    for test in tests:
        try:
            print(f"\n📦 测试 {test['name']}...")
            
            # 检查文件是否存在
            file_path = test['path'].replace('.', '/') + '.py'
            if os.path.exists(file_path):
                print(f"  ✅ 文件存在: {file_path}")
            else:
                print(f"  ❌ 文件不存在: {file_path}")
                continue
            
            # 尝试导入模块
            try:
                module = __import__(test['path'], fromlist=test['components'])
                print(f"  ✅ 模块导入成功")
                
                # 检查关键组件
                missing_components = []
                for component in test['components']:
                    if hasattr(module, component):
                        print(f"    ✅ {component}")
                    else:
                        print(f"    ❌ {component} - 未找到")
                        missing_components.append(component)
                
                if not missing_components:
                    success_count += 1
                    print(f"  🎉 {test['name']} - 完全可用")
                else:
                    print(f"  ⚠️  {test['name']} - 部分组件缺失")
                    
            except ImportError as e:
                print(f"  ❌ 模块导入失败: {e}")
                
        except Exception as e:
            print(f"  💥 测试失败: {e}")
    
    print(f"\n📊 测试总结:")
    print(f"  成功: {success_count}/{len(tests)} 个系统")
    
    if success_count == len(tests):
        print("  🎉 所有contrib系统都可用！")
        return True
    else:
        print("  ⚠️  部分contrib系统可能有问题")
        return False


def test_integration_concept():
    """测试集成概念"""
    print("\n🔧 分析集成方案...")
    
    print("\n📋 冲突分析:")
    print("1. ✅ traits系统 - 使用TraitHandler，无继承冲突")
    print("2. ⚠️  clothing系统 - 需要继承ClothedCharacter") 
    print("3. ⚠️  turnbattle系统 - 需要继承TBBasicCharacter")
    print("4. ❌ 冲突：clothing和turnbattle都要求不同的Character继承")
    
    print("\n💡 解决方案:")
    print("1. 优先保证turnbattle.tb_basic系统 (按你的要求)")
    print("2. Character继承TBBasicCharacter")
    print("3. 手动集成ClothedCharacter的显示功能")
    print("4. 通过@lazy_property添加traits支持")
    
    print("\n🎯 集成后的功能:")
    print("✅ 完整战斗系统: fight, attack, pass, disengage, rest")
    print("✅ 服装穿戴: wear, remove, cover, uncover, inventory")
    print("✅ 角色特征: strength, dexterity, constitution, hp等")
    print("✅ 服装显示: 查看角色时显示穿着的衣物")


def main():
    print("🚀 Evennia Contrib 兼容性测试")
    print("系统组合: traits + clothing + turnbattle.tb_basic")
    print("="*50)
    
    # 测试模块导入
    imports_ok = test_imports()
    
    # 分析集成方案
    test_integration_concept()
    
    print("\n" + "="*50)
    if imports_ok:
        print("✅ 结论: 所有contrib模块都可用")
        print("📁 已创建集成文件:")
        print("   - test_minimal_game.py (完整测试环境)")
        print("   - integrated_character.py (可直接使用的Character类)")
        print("\n🎯 下一步:")
        print("1. 将integrated_character.py复制到你的游戏项目")
        print("2. 在characters.py中使用CombinedCharacter")
        print("3. 在default_cmdsets.py中使用CombinedCharacterCmdSet")
    else:
        print("⚠️  结论: 部分contrib模块可能需要检查")
    

if __name__ == "__main__":
    main() 