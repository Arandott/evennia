"""
Characters

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.

"""

# 导入集成的Character类
from .integrated_character import CombinedCharacter
from .objects import ObjectParent


class Character(ObjectParent, CombinedCharacter):
    """
    The Character class that combines traits, clothing, and turn-based combat.
    
    This Character class now has:
    - Turn-based combat system (fight, attack, pass, disengage, rest)
    - Clothing system (wear, remove, cover, uncover)
    - Traits system (strength, dexterity, constitution, hp)
    
    See mygame/typeclasses/objects.py for a list of
    properties and methods available on all Object child classes like this.
    """

    pass
