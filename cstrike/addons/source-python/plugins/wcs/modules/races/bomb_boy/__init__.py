# ../wcs/modules/races/bomb_boy/__init__.py

# ============================================================================
# >> IMPORTS
# ============================================================================
from random import randint
from time import time

from listeners.tick import Delay
from mathlib import Vector
from entities.constants import MoveType

from ....core.events import Event
from ....core.helpers.overwrites import SayText2
from ....core.modules.races.calls import SkillEvent
from ....core.modules.races.calls import RaceEvent
from ....core.modules.races.manager import race_manager
from ....core.players.entity import Player

# ============================================================================
# >> GLOBAL VARIABLES
# ============================================================================
settings = race_manager.find(__name__)

ALLOWED_WEAPONS = {
    'weapon_knife',
    'weapon_c4',
    'weapon_p90', 
    'weapon_elite', 
    'weapon_flashbang', 
    'weapon_hegrenade', 
    'weapon_smokegrenade'
}

# Messages from strings.ini
site_clearer_message = SayText2(settings.strings['player_skill1'])
bomb_pickup_message = SayText2(settings.strings['player_passive_carrier'])
bomb_dropped_message = SayText2(settings.strings['player_passive_dropped'])
bomb_planted_message = SayText2(settings.strings['player_passive_planted'])

# Effect entry for Bomb Boy's damage skill
site_clearer_effect = settings.get_effect_entry('site_clearer')

# ============================================================================
# >> RACE CALLBACKS
# ============================================================================
@RaceEvent()
def spawncmd(event, wcsplayer):
    player = wcsplayer.player

    wcsplayer.data['bombboy_state'] 	= 1      # 1 = normal, 2 = frozen/invisible
    wcsplayer.data['bombboy_has_bomb'] 	= False

    player.speed = 1.0

    _give_bombboy_loadout(player)

@RaceEvent()
def disconnectcmd(event, wcsplayer):
    pass

@RaceEvent()
def on_skill_desc(wcsplayer, skill_name, kwargs):
    config = settings.config['skills'][skill_name]['variables']

    if skill_name == 'site_clearer':
        chance = config['chance']
        multiplier = config['multiplier']

        kwargs['min_chance'] 	 = chance[0]
        kwargs['max_chance'] 	 = chance[-1]
        kwargs['min_multiplier'] = int(multiplier[0] * 100)
        kwargs['max_multiplier'] = int(multiplier[-1] * 100)

    elif skill_name == 'defensive_position':
        cooldowns = config['cooldown']

        kwargs['min_cooldown'] = cooldowns[0]
        kwargs['max_cooldown'] = cooldowns[-1]


# ============================================================================
# >> SKILL CALLBACKS
# ============================================================================

# DAMAGE SKILL (Site Clearer) -----------------------------------------------
@SkillEvent('pre_take_damage_attacker')
def site_clearer(event, wcsplayer, variables):
    if randint(0, 100) > variables['chance']:
        return

    userid = event['userid']
    wcsvictim = Player.from_userid(userid)

    bonus_damage = event['info'].damage * variables['multiplier']

    wcsvictim.take_delayed_damage(
        bonus_damage,
        wcsplayer.index,
        'bomb_boy-site_clearer'
    )

    vector1 = Vector(*wcsplayer.player.origin)
    vector2 = Vector(*wcsvictim.player.origin)

    vector1.z += 20
    vector2.z += 20

    site_clearer_effect.create(start_point=vector1, end_point=vector2)

    site_clearer_message.send(wcsplayer.index)

@SkillEvent('player_ultimate')
def defensive_position(wcsplayer, variables):
    player = wcsplayer.player
    state = wcsplayer.data.get('bombboy_state', 1)

    # Going INVISIBLE (normal -> frozen / invisible)
    if state == 1:
        now = time()
        cd = variables.get('cooldown', 0)  # per-level cooldown (9..1)

        next_allowed = wcsplayer.data.get('bombboy_next_invis_time', 0)

        if now < next_allowed:
            remaining = int(round(next_allowed - now))
            SayText2(
                f"Defensive Position is on cooldown ({remaining}s remaining)."
            ).send(wcsplayer.index)
            return

        if cd > 0:
            wcsplayer.data['bombboy_next_invis_time'] = now + cd

        # Turn ON: fully invisible, frozen, no weapons
        wcsplayer.data['bombboy_state'] = 2

        wcsplayer.data['bombboy_prev_move_type'] = player.move_type

        player.move_type = MoveType.NONE

        player.color = player.color.with_alpha(0)

        _strip_all_weapons(player)

        SayText2(
            f"You're completely invisible but frozen in place weaponless! (Cooldown: {int(cd)}s)"
        ).send(wcsplayer.index)

    # Going VISIBLE (frozen / invisible -> normal)
    else:
        wcsplayer.data['bombboy_state'] = 1

        prev_move = wcsplayer.data.get('bombboy_prev_move_type')
        if prev_move is not None:
            player.move_type = prev_move
        else:
            player.move_type = MoveType.WALK

        player.color = player.color.with_alpha(255)

        _give_bombboy_loadout(player)

        SayText2(
            "You're no longer frozen or invisible!"
        ).send(wcsplayer.index)

# ============================================================================
# >> BOMB EVENTS
# ============================================================================
@Event('bomb_pickup')
def bomb_pickup(event):
    try:
        userid = event['userid']
    except KeyError:
        return

    if not userid:
        return

    wcsplayer = Player.from_userid(userid)
    player = wcsplayer.player

    wcsplayer.data['bombboy_has_bomb'] = True
    player.speed = 1.25

    bomb_pickup_message.send(wcsplayer.index)

@Event('bomb_dropped')
def bomb_dropped(event):
    try:
        userid = event['userid']
    except KeyError:
        return

    if not userid:
        return

    wcsplayer = Player.from_userid(userid)
    player = wcsplayer.player

    wcsplayer.data['bombboy_has_bomb'] = False
    player.speed = 1.0

    bomb_dropped_message.send(wcsplayer.index)

@Event('bomb_planted')
def bomb_planted(event):
    try:
        userid = event['userid']
    except KeyError:
        return

    if not userid:
        return

    wcsplayer = Player.from_userid(userid)
    player = wcsplayer.player

    wcsplayer.data['bombboy_has_bomb'] = False
    player.speed = 1.4

    bomb_planted_message.send(wcsplayer.index)

# ============================================================================
# >> HELPER FUNCTIONS
# ============================================================================
def _strip_all_weapons(player):
    for weapon in list(player.weapons()):
        if weapon.classname == 'weapon_c4':
            continue
        if weapon.classname == 'weapon_knife':
            continue

        weapon.remove()

def _restrict_weapons(player):
    for weapon in list(player.weapons()):
        if weapon.classname == 'weapon_c4':
            continue
        if weapon.classname == 'weapon_knife':
            continue

        if weapon.classname not in ALLOWED_WEAPONS:
            weapon.remove()

def _give_bombboy_loadout(player):
    _strip_all_weapons(player)
    _restrict_weapons(player)
    player.give_named_item('weapon_p90')
    player.give_named_item('weapon_elite')
    player.give_named_item('weapon_flashbang')
    player.give_named_item('weapon_flashbang')
    player.give_named_item('weapon_hegrenade')
    player.give_named_item('weapon_smokegrenade')