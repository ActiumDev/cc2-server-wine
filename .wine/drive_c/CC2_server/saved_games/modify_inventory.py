#!/usr/bin/python3
# (c) 2024 Actium <51276020+ActiumDev@users.noreply.github.com>
# SPDX-License-Identifier: MIT

import copy
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

# item ids (extracted from v1.5.2) and target quantities for carrier inventory
item_ids_qtys = {
    # Small Munitions
    32: ("Ammo (Flare)",       501),
    33: ("Ammo (20mm)",        20000),
    34: ("Ammo (100mm)",       100),
    35: ("Ammo (120mm Shell)", 100),
    36: ("Ammo (160mm Shell)", 500),
    46: ("Ammo (Sonic Pulse)", 0),
    47: ("Ammo (Smoke)",       0),
    49: ("Ammo (40mm)",        2000),
    1:  ("Ammo (30mm)",        0),

    # Large Munitions
    15: ("Bomb (Light)",             0),
    16: ("Bomb (Medium)",            0),
    17: ("Bomb (Heavy)",             0),
    18: ("Missile (IR)",             50),
    19: ("Missile (Laser)",          0),
    20: ("Missile (AA)",             50),
    30: ("Cruise Missile",           10),
    31: ("Rocket",                   500),
    38: ("Torpedo",                  50),
    39: ("TV-Guided Missile",        10),
    40: ("Torpedo (Noise)",          50),
    41: ("Torpedo (Countermeasure)", 50),

    # Turrets
    10: ("30mm Turret",         0),
    11: ("20mm Autocannon",     12),
    12: ("Rocket Pod",          8),
    13: ("20mm CIWS Turret",    4),
    14: ("IR Missile Launcher", 4),
    27: ("Flare Launcher",      10),
    28: ("100mm Battle Cannon", 0),
    29: ("120mm Artillery Gun", 0),
    48: ("40mm Turret",         4),
    50: ("100mm Heavy Cannon",  0),
    61: ("30mm Gimbal Turret",  0),

    # Utility
    21: ("Observation Camera",         0),
    23: ("Gimbal Camera",              8),
    24: ("Actuated Camera",            0),
    25: ("Radar (AWACS)",              2),
    26: ("Fuel Tank (Aircraft)",       4),
    42: ("Radar",                      0),
    43: ("Sonic Pulse Generator",      0),
    44: ("Smoke Launcher (Stream)",    0),
    45: ("Smoke Launcher (Explosive)", 0),
    51: ("Virus Module",               4),
    60: ("Deployable Droid",           0),

    # Surface Chassis
    2:  ("Seal Chassis",   2),
    3:  ("Walrus Chassis", 2),
    4:  ("Bear Chassis",   0),
    59: ("Mule Chassis",   0),

    # Air Chassis
    5: ("Albatross Chassis", 0),
    6: ("Manta Chassis",     3),
    7: ("Razorbill Chassis", 0),
    8: ("Petrel Chassis",    0),

    # Fuel
    37: ("Fuel (1000L)", 200)
}

class CC2Savegame:
    def __init__(self, file: Path):
        self._file = file

        xml = self._file.read_bytes().decode("ascii")

        # savegame is not a well-formed XML document (no singular root node):
        # https://en.wikipedia.org/wiki/Well-formed_document
        # add root node <save> to enable parsing with ElementTree
        xml_well = xml.removeprefix('<?xml version="1.0" encoding="UTF-8"?>')
        xml_well = f'<?xml version="1.0" encoding="UTF-8"?>\n<save>{xml_well}</save>'

        # parse pre-processed savegame XML
        root = ET.fromstring(xml_well)

        # de-embed XML documents from state attributes
        for node in root.iterfind(".//*[@state]"):
            if not node.attrib["state"].startswith("<?xml"):
                continue

            # parse XML document embedded in state attribute
            state_data = ET.XML(node.attrib["state"])
            # NOTE: ElementTree does not retain whitespace in attributes, so re-indent
            #       https://github.com/python/cpython/issues/61782
            #       >>> elem = ET.fromstring('<test a="   \nab\n    "/>')
            #       >>> print(ET.tostring(elem))
            ET.indent(state_data, space="\t")

            # insert parsed XML document into new <state> element
            state = ET.Element("attrib_state")
            state.insert(0, state_data)
            node.insert(0, state)
            del node.attrib["state"]

        self.root = root

        # selftest: serializing unmodified savegame must yield input
        if str(self) != xml:
            raise RuntimeError("selftest failed: serialization result differs from input file")

    def __str__(self):
        root = copy.deepcopy(self.root)

        # re-embed XML document in state attribute
        for node in root.findall(".//attrib_state/.."):
            state = node.find("attrib_state")
            node.attrib["state"] = '<?xml version="1.0" encoding="UTF-8"?>\n' \
                                 + ET.tostring(state.find("data"), encoding="unicode")
            node.remove(state)

        # serialize XML document
        xml = ET.tostring(root, encoding="unicode")
        # remove <save> element added to make document well-formed
        xml = xml.removeprefix("<save>\n") \
                 .removesuffix("</save>")
        # add XML declaration
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml
        # remove space from empty-element tags
        xml = xml.replace(" />", "/>") \
                 .replace(" /&gt;", "/&gt;")
        # reformat state attributes to match CC2 save format
        xml = re.sub(r'state="(&lt;\?xml .+?)"',
                     lambda m: "state='"
                               + m.group(1).replace("&quot;", "\"")
                                           .replace("&#10;", "\n")
                                           .replace("&#09;", "\t")
                               + "\n\n'",
                     xml, flags=re.DOTALL)

        return xml

    def write(self) -> None:
        # rename savegame to backup file and write modified savegame
        self._file.replace(Path(f"{self._file}~"))
        self._file.write_bytes(str(self).encode("ascii"))

# read savegame
slot = input("Enter savegame folder (e.g., 'slot_0'): ").rstrip()
sav_file = Path(os.getenv("APPDATA"), "Carrier Command 2", "saved_games", slot, "save.xml")
sav = CC2Savegame(sav_file)
print()

# find player team id
non_ai_teams = sav.root.findall('scene/teams/teams/t[@is_ai_controlled="false"]')
if len(non_ai_teams) == 0:
    raise RuntimeError("found zero player-controlled teams")
elif len(non_ai_teams) > 1:
    raise RuntimeError("found multiple player-controlled teams")
else:
    team_id = non_ai_teams[0].attrib["id"]

# find player carrier vehicle id
player_carriers = sav.root.findall(f'vehicles/vehicles/v[@definition_index="0"][@team_id="{team_id}"]')
if len(player_carriers) == 0:
    raise RuntimeError("found zero player-controlled carriers")
elif len(player_carriers) > 1:
    raise RuntimeError("found multiple player-controlled carriers")
else:
    carrier_id = player_carriers[0].attrib["id"]

# iterate over quantities
changed = False
print("Pending inventory changes:")
state = sav.root.find(f'vehicles/vehicle_states/v[@id="{carrier_id}"]/attrib_state')
for item_id, item in enumerate(state.iterfind("data/inventory/item_quantities/q"), 1):
    try:
        if int(item.attrib["value"]) == item_ids_qtys[item_id][1]:
            continue

        changed = True
        print(f'{item_id:2d}: {item_ids_qtys[item_id][0]:24s}: ' +
              f'{int(item.attrib["value"]):5d} -> {item_ids_qtys[item_id][1]:5d}')
        item.attrib["value"] = str(item_ids_qtys[item_id][1])
    except KeyError:
        continue

if not changed:
    print("NONE")
    input("Press ENTER to exit ...")
    sys.exit(0)

print()
input("Press ENTER to apply above changes or CTRL+C to abort ...")
sav.write()

input("Savegame modified. Press ENTER to exit ...")
sys.exit(0)
