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
import itertools
import decimal
import sys
sys.path.append('../../python-poly2tri')
import p2t
sys.path.remove('../../python-poly2tri')
from generalfuncs import pairwise

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

def convert_polyline_to_polytri_version(polyline):
    """Converts points to p2t points that poly2tri can deal with
    This function accepts tuples or fontforge points"""
    result = []
    if hasattr(polyline, 'coords'):
        polyline = polyline.coords
    for point in polyline:
        try:
            x, y = point.x, point.y
        except AttributeError:
            x, y = point[0], point[1]
        result.append(p2t.Point(x, y))
    return result

def closedpolyline2vectorset(polyline):
    """Converts a polyline (which should be closed, i.e. the last point = the first point) to a set of vectors (as Decimal tuple pairs)."""
    result = set()
    l = list(polyline)  # Just in case it was a generator before...
    for a, b in pairwise(l):
        vector = [p2dt(a), p2dt(b)]
        vector = tuple(sorted(vector))
        result.add(vector)
    return result

def triangles2vectorset(triangles):
    result = set()
    for t in triangles:
        for v in triangle2vectors(t):
            result.add(v)
    return result

def vectorpairs_to_pointlist(pairs):
    """This function takes a list of pairs of points and turns it into a single list of points.
    This function needs to be updated when we subdivide bezier curves"""
    pairs = list(pairs)
    if not pairs:
        return []
    return [pair[0] for pair in pairs] + [pairs[-1][-1]]

def triangle2vectors(t):
    """Converts a triangle object into a list of three vectors (which are pairs of Decimal tuples)."""
    v1 = [p2dt(t.a), p2dt(t.b)]
    v2 = [p2dt(t.b), p2dt(t.c)]
    v3 = [p2dt(t.c), p2dt(t.a)]
    v1 = tuple(sorted(v1))
    v2 = tuple(sorted(v2))
    v3 = tuple(sorted(v3))
    return [v1, v2, v3]

epsilon_decimal = decimal.Decimal('1e-9')
def p2dt(point):
    """Converts a point into a representation using a tuple of Python's Decimal objects."""
    try:
        x, y = point.x, point.y
    except AttributeError:
        x, y = point[0], point[1]
    dx = decimal.Decimal(x).quantize(epsilon_decimal, decimal.ROUND_HALF_UP)
    dy = decimal.Decimal(y).quantize(epsilon_decimal, decimal.ROUND_HALF_UP)
    return (dx, dy)

