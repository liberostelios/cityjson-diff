import json

import click
from deepdiff import Delta
from deepdiff.serialization import pretty_print_diff
from rich.console import Console

from cityjson import dereference_citymodel

@click.command()
@click.argument("source", type=click.File('r'))
@click.argument("delta", type=click.File('rb'))
@click.argument("dest", type=click.File('w'))
def cli(source, delta, dest):
    console = Console()
    console.rule("[blue]CityJSON patch 🩹")

    cm = json.load(source)

    console.print(f"Applying patch to {source.name} ({len(cm['CityObjects'])} objects)...")

    _ = dereference_citymodel(cm.copy())

    d = Delta(delta_file=delta)

    # console.print(pretty_print_diff(d.diff))

    result = cm + d

    console.print(f"[green]DONE![/green] Result contains {len(result['CityObjects'])} objects.")

    json.dump(result, dest)

if __name__ == "__main__":
    cli()