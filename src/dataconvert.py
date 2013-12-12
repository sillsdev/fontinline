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
        # It's a LineString or LinearRing
        return pointlist.coords
    else:
        # It might be a generator
        pointlist = list(pointlist)
        if not pointlist:
            # It's an empty list
            return []
        elif hasattr(pointlist[0], 'x'):
            # It's a list of FontForge (or p2t) points
            return [(p.x, p.y) for p in pointlist]
        else:
            # It was already a list of tuples
            return pointlist

def any_to_linestring(pointlist):
    try:
        return LineString(any_to_polyline(pointlist))
    except ValueError:
        print str(list(pointlist))
        raise

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
    """This function takes a list of pairs of points and turns it into a
    list of lists of points. Each list will be a slice of the points such
    that none of the pairs of consecutive points were not in pairs. The
    number of lists should be equal to the number of pairs removed."""
    pairs = list(pairs)
    if not pairs:
        return []
    i=0
    pointlist=[]
    while i<len(pairs):
        idx=0
        pointlist.append([])
        pointlist[0].append(pairs[i][0])
        boolean=True
        while boolean:
            pointlist[idx].append(pairs[i][1])
            if i!=len(pairs)-1:
                boolean = boolean or pairs[i][1] == pairs[i+1][0]
            i=i+1
    return pointlist

def vectorpairs_to_linestring(pairs):
    """This function takes a list of pairs of points and turns it into a single LineString."""
    points = list(vectorpairs_to_pointlist(pairs))
    if points[0] == points[-1]:
        del points[-1]
    return any_to_linestring(points)

def triangle2vectors(t):
    """Converts a triangle object into a list of three vectors (which are pairs of Decimal tuples)."""
    v1 = [p2dt(t.a), p2dt(t.b)]
    v2 = [p2dt(t.b), p2dt(t.c)]
    v3 = [p2dt(t.c), p2dt(t.a)]
    v1 = tuple(sorted(v1))
    v2 = tuple(sorted(v2))
    v3 = tuple(sorted(v3))
    return [v1, v2, v3]

def triangle2lines(t):
    l1 = [p2ft(t.a), p2ft(t.b)]
    l2 = [p2ft(t.b), p2ft(t.c)]
    l3 = [p2ft(t.c), p2ft(t.a)]
    return [l1, l2, l3]

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

def p2ft(point):
    """Converts a point into a representation using a tuple of float objects."""
    try:
        x, y = point.x, point.y
    except AttributeError:
        x, y = point[0], point[1]
    return (x, y)
