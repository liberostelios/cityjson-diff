import json

import click
from rich.console import Console

import hashlib
from deepdiff import DeepDiff, Delta
from deepdiff.path import extract

def validate_cityjson(data):
    """Return True if the data provided is a CityJSON city model"""
    return data['type'] == "CityJSON"

def dereference_list(l, verts):
    """Returns the values of the list dereferenced"""
    result = []

    for i in l:
        if isinstance(i, list):
            result.append(dereference_list(i, verts))
        else:
            result.append([round(float(c), 3) for c in verts[i]])
    
    return result

def dereference_geometry(geom, verts):
    """Returns the geometry with its vertices dereferenced"""
    if not "boundaries" in geom:
        return geom
    
    result = dereference_list(geom["boundaries"], verts)

    geom["boundaries"] = result

    return geom

def dereference_cityobject(obj, verts):
    """Returns the city object with its vertices dereferenced"""
    result = []
    geoms = obj["geometry"]
    
    for geom in geoms:
        result.append(dereference_geometry(geom, verts))
    
    obj["geometry"] = result

    return obj

def hash_object(obj):
    """Returns the hash of an object"""
    encoded = json.dumps(obj).encode('utf-8')
    m = hashlib.new('sha1')
    m.update(encoded)

    return m.hexdigest()

def transform_vertices(verts, transform) -> list:
    """Returns the list of vertices transformed back to their original values"""
    result = []

    t = transform["translate"]
    s = transform["scale"]

    return [[coords[0] * s[0] + t[0],
             coords[1] * s[1] + t[1],
             coords[2] * s[2] + t[2]]
             for coords in verts]

def dereference_citymodel(cm):
    """Returns the city model with the vertices of the city objects dereferenced"""
    result = {}

    verts = cm["vertices"]

    if "transform" in cm:
        verts = transform_vertices(verts, cm["transform"])

    for co_id, co in cm["CityObjects"].items():
        new_co = dereference_cityobject(co, verts)
        result[co_id] = hash_object(new_co)
    
    cm["CityObjects"] = result

    del cm["vertices"]

    return cm

def print_diff(co_id_src, co_id_dest, source, dest, console) -> dict:
    """Prints the diff of a given city object"""
    if co_id_src is None:
        source_co = {}
    else:
        source_co = extract(source, co_id_src)
    if co_id_dest is None:
        dest_co = {}
    else:
        dest_co = extract(dest, co_id_dest)

    co_diff = DeepDiff(source_co, dest_co, ignore_order=True)

    if len(co_diff) == 0:
        return co_diff.to_dict()

    console.print("")
    if not co_id_src is None:
        console.print(f"[b]--- {co_id_src.replace('root', 'a')} [/b]")
    if not co_id_dest is None:
        console.print(f"[b]+++ {co_id_dest.replace('root', 'b')} [/b]")

    if "values_changed" in co_diff:
        for path, change in co_diff["values_changed"].items():
            console.print(f"[cyan]@@ {path.replace('root', '')} @@[/cyan] [yellow]changed")

            console.print(f"-{change['old_value']}", style="red", highlight=False)
            console.print(f"+{change['new_value']}", style="green", highlight=False)
    
    if "type_changes" in co_diff:
        for path, change in co_diff["type_changes"].items():
            console.print(f"[cyan]@@ {path.replace('root', '')} @@[/cyan] [yellow]changed")

            console.print(f"-{change['old_value']}", style="red", highlight=False)
            console.print(f"+{change['new_value']}", style="green", highlight=False)
    
    if "dictionary_item_removed" in co_diff:
        for path in co_diff["dictionary_item_removed"]:
            console.print(f"[cyan]@@ {path.replace('root', '')} @@[/cyan] [red]deleted[/red]")

            console.print(f"-{extract(source_co, path)}", style="red", highlight=False)
    
    if "dictionary_item_added" in co_diff:
        for path in co_diff["dictionary_item_added"]:
            console.print(f"[cyan]@@ {path.replace('root', '')} @@[/cyan] [green]added[/green]")

            console.print(f"+{extract(dest_co, path)}", style="green", highlight=False)

    if any([not (x == "values_changed" or x == "dictionary_item_removed" or x == "dictionary_item_added" or x == "type_changes") for x in co_diff]):
        console.print(co_diff)

    return co_diff.to_dict()

def fix_path(d, path) -> dict:
    result = {}

    for p in d:
        result[p.replace('root', path)] = d[p]

    return result

def remaster_diff(diff, path) -> object:
    """Returns the same diff, but with the root replace by the given path"""
    if "values_changed" in diff:
        diff["values_changed"] = fix_path(diff["values_changed"], path)
    
    if "type_changes" in diff:
        diff["type_changes"] = fix_path(diff["type_changes"], path)
    
    if "dictionary_item_removed" in diff:
        diff["dictionary_item_removed"] = fix_path(diff["dictionary_item_removed"], path)

    if "dictionary_item_added" in diff:
        diff["dictionary_item_added"] = fix_path(diff["dictionary_item_added"], path)
    
    return diff

# From https://stackoverflow.com/questions/20656135/python-deep-merge-dictionary-data
def merge(source, destination):
    """
    run me with nosetests --with-doctest file.py

    >>> a = { 'first' : { 'all_rows' : { 'pass' : 'dog', 'number' : '1' } } }
    >>> b = { 'first' : { 'all_rows' : { 'fail' : 'cat', 'number' : '5' } } }
    >>> merge(b, a) == { 'first' : { 'all_rows' : { 'pass' : 'dog', 'fail' : 'cat', 'number' : '5' } } }
    True
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge(value, node)
        else:
            destination[key] = value

    return destination

@click.command()
@click.argument('source', type=click.File('r'))
@click.argument('dest', type=click.File('r'))
@click.option('-r', '--reverse', is_flag=True)
@click.option('-s', '--slow', is_flag=True)
@click.option('-o', '--output', type=click.File('wb'))
def cli(source, dest, reverse, slow, output):
    """Main command"""
    console = Console()

    console.rule("[blue]CityJSON diff")
    console.print(f'Comparing (a) [red]{source.name}[/red] -> (b) [green]{dest.name}[/green] :raised_hands:\n')

    if reverse:
        source, dest = dest, source

    cm_source = json.load(source)
    cm_dest = json.load(dest)

    cm_source_hash = dereference_citymodel(cm_source.copy())
    cm_dest_hash = dereference_citymodel(cm_dest.copy())

    # console.print(cm)

    # console.print(f"{source.name} has {len(cm_source['CityObjects'])} objects!")

    if slow:
        with console.status("[bold green]Computing slow differences...") as status:
            diff = DeepDiff(cm_source, cm_dest, exclude_paths="root['vertices']", cache_size=5000)

            console.print(diff)

            if not output is None:
                Delta(diff).dump(output)
    else:
        with console.status("[bold green]Computing fast differences...") as status:
            diff = DeepDiff(cm_source_hash, cm_dest_hash, cache_size=5000, get_deep_distance=True)

            all_diff = {}

            if "values_changed" in diff:
                for co_id in diff["values_changed"]:
                    new_diff = print_diff(co_id, co_id, cm_source, cm_dest, console)
                    all_diff = merge(remaster_diff(new_diff, co_id), all_diff)
            
            if "dictionary_item_removed" in diff:
                for co_id in diff["dictionary_item_removed"]:
                    print_diff(co_id, None, cm_source, cm_dest, console)
                    all_diff.setdefault("dictionary_item_removed", {})[co_id] = extract(cm_source, co_id)

            if "dictionary_item_added" in diff:
                for co_id in diff["dictionary_item_added"]:
                    print_diff(None, co_id, cm_source, cm_dest, console)
                    all_diff.setdefault("dictionary_item_added", {})[co_id] = extract(cm_dest, co_id)

if __name__ == "__main__":
    cli()