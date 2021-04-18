from nbt import nbt

from tqdm import tqdm

from pathlib import Path

import json
import urllib.request

cached_player_names = {}

def get_name(item):
    if 'tag' not in item:
        return None

    tag = item['tag']

    if 'display' not in tag or 'Name' not in tag['display']:
        return None

    # Display names are stored in JSON format
    name = json.loads(tag['display']['Name'].value)

    if 'text' not in name:
        return None

    return name['text']

def is_important_item(item):
    if 'id' not in item:
        return False

    id = item['id'].value
    name = get_name(item)

    if name is not None:
        return True

    keywords = ['netherite', 'ancient_debris', 'shulk']

    for keyword in keywords:
        if keyword in id:
            return True

    return False

def get_important_chunk_items(chunk):
    INVENTORY_NAMES = ['Items', 'ArmorItems', 'HandItems']

    level = chunk['Level']
    entities = level['Entities']
    tile_entities = level['TileEntities']

    if len(entities) == 0 and len(tile_entities) == 0:
        return []

    position_item = []

    # Check entity items
    for entity in entities:
        pos = tuple([x.value for x in entity['Pos']])

        # Check for items in multiple inventories, namely:
        # 'Items' for minecarts, llamas/horses/donkeys/mules/etc
        # 'ArmorItems' for armor stands, zombies/skeletons/etc
        # 'HandItems' for armor stands, zombies/skeletons/etc
        for inventory_name in INVENTORY_NAMES:
            if inventory_name in entity:
                for item in entity[inventory_name]:
                    if is_important_item(item):
                        position_item.append((pos, item))

        # Item frames hold one item as 'Item'
        if 'Item' in entity and is_important_item(entity['Item']):
            position_item.append((pos, entity['Item']))

    # Check tile entity items
    for tile_entity in tile_entities:
        if not 'Items' in tile_entity:
            continue

        x = tile_entity['x'].value
        y = tile_entity['y'].value
        z = tile_entity['z'].value
        pos = (x, y, z)

        for item in tile_entity['Items']:
            if is_important_item(item):
                position_item.append((pos, item))

    return position_item

def search_players(playerdata_dir):
    player_inventory = {}

    for playerdata_path in tqdm(playerdata_dir.glob("*.dat")):
        nbtfile = nbt.nbt.NBTFile(playerdata_path, "rb")

        player_name = playerdata_path.with_suffix('').name

        if 'bukkit' in nbtfile and 'lastKnownName' in nbtfile['bukkit']:
            player_name = nbtfile['bukkit']['lastKnownName']

            uuid = playerdata_path.with_suffix('').name
            cached_player_names[uuid] = player_name

        player_matches = []

        for inventory_type in ['Inventory', 'EnderItems']:
            inventory = nbtfile[inventory_type]

            for item in inventory:
                if is_important_item(item):
                    player_matches.append(item)

        if len(player_matches) > 0:
            player_inventory[player_name] = player_matches

    return player_inventory

def search_stats(stats_dir):
    player_debris_mined = []

    for file in tqdm(stats_dir.glob("*.json")):
        with open(file, "r") as f:
            text = f.read()

        data = json.loads(text)

        stats = data['stats']

        if 'minecraft:mined' not in stats:
            continue

        mined = stats['minecraft:mined']

        if 'minecraft:ancient_debris' not in mined:
            continue

        mined_count = mined['minecraft:ancient_debris']

        uuid = file.with_suffix('').name

        name = cached_player_names.get(uuid, None)

        if name is None:
            url = urllib.request.urlopen(f"https://api.mojang.com/user/profiles/{uuid}/names")
            contents = json.loads(url.read().decode("utf-8"))
            name = contents[-1]['name']

        player_debris_mined.append((name, mined_count))

    return player_debris_mined

def search_world(world_dir):
    if not world_dir.exists():
        print(f"World at {str(world_dir)} does not exist")

        return

    print(f"Searching world at {str(world_dir)}")

    try:
        world = nbt.world.WorldFolder(world_dir)
    except Exception as e:
        print(f"Failed to open world at {str(world_dir)}")

        return

    position_item = []

    progress_bar = tqdm(world.iter_regions(),
        total=len(world.get_regionfiles()))

    for region in progress_bar:
        progress_bar.set_description(f"Region {region.loc.x}, {region.loc.z}")

        chunk_count = len(region.get_metadata())
        chunk_iter = region.iter_chunks()

        if chunk_count > 1024:
            chunk_iter = tqdm(chunk_iter, total=chunk_count, leave=False)

        for chunk in chunk_iter:
            position_item += get_important_chunk_items(chunk)

    return position_item

def main():
    saves_dir = Path.home() / Path("AppData/Roaming/.minecraft/saves/")
    world_dir = saves_dir / "2021-04-12/"
    nether_dir = world_dir / "DIM-1/"
    end_dir = world_dir / "DIM1/"

    playerdata_dir = world_dir / "./playerdata/"
    stats_dir = world_dir / "./stats/"

    for path in [world_dir, nether_dir, end_dir, playerdata_dir, stats_dir]:
        if not path.exists():
            print(f"Cannot find path '{str(path)}'")

            return

    dimension_position_item = [
        ("overworld", search_world(world_dir)),
        ("nether", search_world(nether_dir)),
        ("end", search_world(end_dir))
    ]
    player_inventory = search_players(playerdata_dir)
    player_debris_mined = search_stats(stats_dir)

    output = []

    for dimension, position_item in dimension_position_item:
        output.append(dimension)

        for position, item in position_item:
            id = item['id'].value
            name = get_name(item)
            count = item['Count'].value

            pos_str = ' '.join([f"{x:.02f}" for x in position])

            output.append(f"\t({pos_str}) {id}")

            if name:
                output.append(f"\t\t{name}")

            if count > 1:
                output.append(f"\t\t{count}")

    for player, inventory in player_inventory.items():
        output.append(player)

        for item in inventory:
            output.append(f"\t{item['id'].value}")

            name = get_name(item)
            count = item['Count'].value

            if name is not None:
                output.append(f"\t\t{name}")

            if count > 1:
                output.append(f"\t\t{count}")

    for player, debris_mined in player_debris_mined:
        output.append(f"{player} mined {debris_mined} debris")

    with open("output.txt", "wb") as f:
        s = '\n'.join([str(x) for x in output])

        f.write(s.encode("utf8"))

if __name__ == "__main__":
    main()
