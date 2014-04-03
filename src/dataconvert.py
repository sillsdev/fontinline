from __future__ import division

"""Library for converting lines and polygons between various formats

Formats used in our code:
    polyline - a list of (x, y) tuples.
    ffpointlist - a list of FontForge Point objects (with .x and .y attributes)
    LineString - a shapely.geometry.LineString object
        linestring.coords acts like a list of (x, y) tuples
    Polygon - a shapely.geometry.Polygon object
        polygon.exterior is a LinearRing (like a closed LineString) of the outside
        polygon.interiors is a list of LinearRings, one per "hole"
        In both cases, use coords to get lists of tuples, e.g.:
            polygon.exterior.coords
            (hole.coords for hole in polygon.interiors)
"""

from shapely.geometry import Point, LineString, Polygon
import itertools
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

def any_to_closedpolyline(pointlist):
    line = list(any_to_polyline(pointlist))
    if line[0] != line[-1]:
        line.append(line[0])
    return line

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

def vectorpairs_to_pointlist(pairs):
    """This function takes a list of pairs of points and turns it into a
    list of lists of points. Each list will be a slice of the points such
    that none of the pairs of consecutive points were not in pairs. The
    number of lists should be equal to the number of pairs removed."""
    pairs = list(pairs)
    if not pairs:
        return []
    return [pair[0] for pair in pairs] + [pairs[-1][-1]]

def vectorpairs_to_linestring(pairs):
    """This function takes a list of pairs of points and turns it into a single LineString."""
    points = list(vectorpairs_to_pointlist(pairs))
    if points[0] == points[-1]:
        del points[-1]
    return any_to_linestring(points)

def triangle2lines(t):
    l1 = [p2ft(t.a), p2ft(t.b)]
    l2 = [p2ft(t.b), p2ft(t.c)]
    l3 = [p2ft(t.c), p2ft(t.a)]
    return [l1, l2, l3]

def p2ft(point):
    """Converts a point into a representation using a tuple of float objects."""
    try:
        x, y = point.x, point.y
    except AttributeError:
        x, y = point[0], point[1]
    return (x, y)
