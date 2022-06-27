import json

import click
from rich.console import Console

import hashlib
from deepdiff import DeepDiff

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
            result.append(verts[i])
    
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

def dereference_citymodel(cm):
    """Returns the city model with the vertices of the city objects dereferenced"""
    result = {}

    verts = cm["vertices"]

    for co_id, co in cm["CityObjects"].items():
        new_co = dereference_cityobject(co, cm["vertices"])
        result[co_id] = hash_object(new_co)
    
    cm["CityObjects"] = result

    del cm["vertices"]

    return cm

@click.command()
@click.argument('source', type=click.File('r'))
@click.argument('dest', type=click.File('r'))
def cli(source, dest):
    """Main command"""
    console = Console()

    console.rule("[blue]CityJSON diff")
    console.print(f'Comparing files [red]{source.name}[/red] -> [green]{dest.name}[/green] :raised_hands:')

    cm_source = json.load(source)
    cm_dest = json.load(dest)

    cm_source = dereference_citymodel(cm_source)
    cm_dest = dereference_citymodel(cm_dest)

    # console.print(cm)

    # console.print(f"{source.name} has {len(cm_source['CityObjects'])} objects!")

    with console.status("[bold green]Computing differences...") as status:
        diff = DeepDiff(cm_source, cm_dest, ignore_order=True, cache_size=5000, get_deep_distance=True)

        console.print(diff)

if __name__ == "__main__":
    cli()