"""Module with CityJSON specific functions"""

import hashlib
import json

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