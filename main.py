from nbt import nbt

from tqdm import tqdm

from pathlib import Path

import json
import urllib.request

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

def is_important(item):
    if 'id' not in item:
        return False

    id = item['id'].value
    name = get_name(item)

    keywords = ['netherite', 'ancient_debris', 'shulk']

    for keyword in keywords:
        if keyword in id:
            return True

    if name is not None:
        return True

    return False

def search_players(playerdata_dir):
    player_inventory = {}

    for playerdata_path in tqdm(playerdata_dir.glob("*.dat")):
        nbtfile = nbt.nbt.NBTFile(playerdata_path, "rb")

        player_name = playerdata_path.with_suffix('').name

        if 'bukkit' in nbtfile and 'lastKnownName' in nbtfile['bukkit']:
            player_name = nbtfile['bukkit']['lastKnownName']

        player_matches = []

        for inventory_type in ['Inventory', 'EnderItems']:
            inventory = nbtfile[inventory_type]

            for item in inventory:
                if is_important(item):
                    player_matches.append(item)

        if len(player_matches) > 0:
            player_inventory[player_name] = player_matches

    return player_inventory

def search_world(world_dir):
    if not world_dir.exists():
        print(f"World at {str(world_dir)} does not exist")

        return

    print(f"Searching world at {str(world_dir)}")

    world = nbt.world.WorldFolder(world_dir)

    position_item = []

    inventory_names = ['Items', 'ArmorItems', 'HandItems']

    region_iter = tqdm(world.iter_regions(), total=len(world.get_regionfiles()),
        desc="Getting regions", leave=False)

    regions = [x for x in region_iter]

    for region in regions:
        chunk_count = len(region.get_metadata())
        chunk_iter = region.iter_chunks()

        if chunk_count > 100:
            chunk_iter = tqdm(chunk_iter, total=chunk_count, leave=False)

        for chunk in chunk_iter:
            level = chunk['Level']

            # Check entity items
            for entity in level['Entities']:
                pos = tuple([x.value for x in entity['Pos']])

                # Check for items in multiple inventories, namely:
                # 'Items' for minecarts, llamas/horses/donkeys/mules/etc
                # 'ArmorItems' for armor stands, zombies/skeletons/etc
                # 'HandItems' for armor stands, zombies/skeletons/etc
                for inventory_name in inventory_names:
                    if inventory_name in entity:
                        for item in entity[inventory_name]:
                            if is_important(item):
                                position_item.append((pos, item))

                # Item frames hold one item as 'Item'
                if 'Item' in entity and is_important(entity['Item']):
                    position_item.append((pos, entity['Item']))

            # Check tile entity items
            for tile_entity in level['TileEntities']:
                if not 'Items' in tile_entity:
                    continue

                x = tile_entity['x'].value
                y = tile_entity['y'].value
                z = tile_entity['z'].value
                pos = (x, y, z)

                for item in tile_entity['Items']:
                    if is_important(item):
                        position_item.append((pos, item))

    return position_item

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
        url = urllib.request.urlopen(f"https://api.mojang.com/user/profiles/{uuid}/names")
        contents = json.loads(url.read().decode("utf-8"))
        name = contents[-1]['name']

        player_debris_mined.append((name, mined_count))

    return player_debris_mined

def main():
    saves_dir = Path("C:/Users/alext/AppData/Roaming/.minecraft/saves/")
    world_dir = saves_dir / "./2021-03-15/"
    nether_dir = world_dir / "./DIM-1/"
    end_dir = world_dir / "./DIM1/"

    playerdata_dir = world_dir / "./playerdata/"
    stats_dir = world_dir / "./stats/"

    for path in [world_dir, nether_dir, end_dir, playerdata_dir, stats_dir]:
        if not path.exists():
            print(f"Cannot find path '{str(path)}'")

            return

    dimension_position_item = {
        "overworld": search_world(world_dir),
        "nether": search_world(nether_dir),
        "end": search_world(end_dir)
    }
    player_inventory = search_players(playerdata_dir)
    player_debris_mined = search_stats(stats_dir)

    output = []

    for dimension, position_item in dimension_position_item.items():
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

    with open("output.txt", "w") as f:
        f.write('\n'.join([str(x) for x in output]))

if __name__ == "__main__":
    main()
