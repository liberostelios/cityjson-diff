import json

import click
from rich.console import Console

from deepdiff import DeepDiff, Delta
from deepdiff.path import extract

from cityjson import dereference_citymodel

def get_cityobject_diff(co_id_src, co_id_dest, source, dest) -> dict:
    """Prints the diff of a given city object"""
    if co_id_src is None:
        source_co = {}
    else:
        source_co = extract(source, co_id_src)
    if co_id_dest is None:
        dest_co = {}
    else:
        dest_co = extract(dest, co_id_dest)

    co_diff = DeepDiff(source_co, dest_co, ignore_order=True, report_repetition=True)

    return co_diff

def print_cityobject_diff(path_src, path_dest, co_diff, console):
    console.print("")
    if not path_src is None:
        console.print(f"[b]--- {path_src.replace('root', 'a')} [/b]")
    if not path_dest is None:
        console.print(f"[b]+++ {path_dest.replace('root', 'b')} [/b]")

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

            console.print(f"-{extract(co_diff.t1, path)}", style="red", highlight=False)
    
    for path in co_diff.get("iterable_item_removed", {}):
        console.print(f"[cyan]@@ {path.replace('root', '')} @@[/cyan] [red]deleted[/red]")

        console.print(f"-{extract(co_diff.t1, path)}", style="red", highlight=False)
    
    if "dictionary_item_added" in co_diff:
        for path in co_diff["dictionary_item_added"]:
            console.print(f"[cyan]@@ {path.replace('root', '')} @@[/cyan] [green]added[/green]")

            console.print(f"+{extract(co_diff.t2, path)}", style="green", highlight=False)
    
    for path in co_diff.get("iterable_item_added", {}):
        console.print(f"[cyan]@@ {path.replace('root', '')} @@[/cyan] [green]added[/green]")

        console.print(f"+{extract(co_diff.t2, path)}", style="green", highlight=False)

    # if any([not (x == "values_changed" or x == "dictionary_item_removed" or x == "dictionary_item_added" or x == "type_changes") for x in co_diff]):
    #     console.print(co_diff)

def fix_path(d, path) -> dict:
    if isinstance(d, dict):
        result = {}

        for p in d:
            result[p.replace('root', path)] = d[p]

        return result
    
    result = []
    for p in d:
        result.append(p.replace('root', path))
    
    return result

def remaster_diff(diff, path) -> object:
    """Returns the same diff, but with the root replace by the given path"""
    if "values_changed" in diff:
        diff["values_changed"] = fix_path(diff["values_changed"], path)
    
    if "type_changes" in diff:
        diff["type_changes"] = fix_path(diff["type_changes"], path)
    
    if "dictionary_item_removed" in diff:
        diff["dictionary_item_removed"] = fix_path(diff["dictionary_item_removed"], path)

    if "iterable_item_removed" in diff:
        diff["iterable_item_removed"] = fix_path(diff["iterable_item_removed"], path)

    if "dictionary_item_added" in diff:
        diff["dictionary_item_added"] = fix_path(diff["dictionary_item_added"], path)
    
    if "iterable_item_added" in diff:
        diff["iterable_item_added"] = fix_path(diff["iterable_item_added"], path)
    
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

    console.rule("[blue]CityJSON diff ✂️")
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
                if len(diff["values_changed"]) > 2:
                    console.print(f"[orange]Too many object changed {len(diff['values_changed'])}! Will only show 2...[/orange]")

                for path in list(diff["values_changed"].keys())[:2]:
                    new_diff = get_cityobject_diff(path, path, cm_source, cm_dest)
                    print_cityobject_diff(path, path, new_diff, console)
                    all_diff = merge(remaster_diff(new_diff, path), all_diff)
            
            if "dictionary_item_removed" in diff:
                for path in diff["dictionary_item_removed"]:
                    new_diff = get_cityobject_diff(path, None, cm_source, cm_dest)
                    print_cityobject_diff(path, None, new_diff, console)
                    all_diff.setdefault("dictionary_item_removed", []).append(path)

            if "dictionary_item_added" in diff:
                for path in diff["dictionary_item_added"]:
                    new_diff = get_cityobject_diff(None, path, cm_source, cm_dest)
                    print_cityobject_diff(None, path, new_diff, console)
                    all_diff.setdefault("dictionary_item_added", []).append(path)
            
            if not output is None:
                Delta(new_diff).dump(output)

if __name__ == "__main__":
    cli()