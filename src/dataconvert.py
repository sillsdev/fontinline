"""Library for converting lines and polygons between various formats

Formats used in our code:
    polyline - a list of (x,y) tuples.
    ffpointlist - a list of FontForge Point objects (with .x and .y attributes)
    LineString - a shapely.geometry.LineString object
        linestring.coords acts like a list of (x,y) tuples
    Polygon - a shapely.geometry.Polygon object
        polygon.exterior is a LinearRing (like a closed LineString) of the outside
        polygon.interiors is a list of LinearRings, one per "hole"
        In both cases, use coords to get lists of tuples, e.g.:
            polygon.exterior.coords
            (hole.coords for hole in polygon.interiors)
"""

from shapely.geometry import Point, LineString, Polygon

def any_to_polyline(pointlist):
    """Given a point list in any format, convert it to a polyline."""
    if hasattr(pointlist, 'exterior'):
        # It's a Polygon; just return the *outside* line
        return pointlist.exterior.coords
    elif hasattr(pointlist, 'coords'):
        # It's a LineString
        return pointlist.coords
    elif not pointlist:
        # It's an empty list
        return []
    elif hasattr(pointlist[0], 'x'):
        # It's a list of FontForge (or p2t) points
        return [(p.x, p.y) for p in pointlist]
    else:
        # It was already a list of tuples
        return pointlist

def any_to_linestring(pointlist):
    return LineString(any_to_polyline(pointlist))

def any_to_polygon(outside, holes):
    outside = any_to_polyline(outside)
    holes = map(any_to_polyline, holes)
    return Polygon(outside, holes)

def ff_to_tuple(ffpointlist):
    """This function takes a list of fontforge points and turns it into a list of tuples.
    This function needs to be updated to retain the oncurve-offcurve information"""
    # TODO: Try to eliminate the need for this function
    try:
        return [(p.x, p.y) for p in ffpointlist]
    except AttributeError:
        return ffpointlist  # Because this was probably already a list of tuples
    except TypeError:
        # This would be TypeError: 'LineString' object is not iterable
        return ffpointlist.coords

