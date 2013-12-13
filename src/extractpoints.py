#!/usr/bin/env python

import fontforge
import time
import optparse
import argparse
import sys
import os, os.path
import itertools
import functools
import collections
import shapely
import warnings
import math
from shapely.geometry import Polygon, LineString, Point
sys.path.append('../../python-poly2tri')
import p2t
sys.path.remove('../../python-poly2tri')

from dataconvert import (
    any_to_linestring, any_to_polygon, any_to_polyline, any_to_closedpolyline, ff_to_tuple,
    convert_polyline_to_polytri_version,
    triangle2lines, vectorpairs_to_pointlist, vectorpairs_to_linestring,
)
from visualization import (
    setup_screen, draw_all, draw_midlines, wait_for_keypress, red, green, blue,
    draw_fat_point,
)
from generalfuncs import (
    pairwise, by_threes,
    vectorlengthastuple, vectorlength, are_points_equal, are_lines_equal,
    averagepoint_as_ffpoint, averagepoint_as_tuple, averagepoint_as_tuplevector,
    comp, itermap, iterfilter, iterfilter_stopatvectors, itermap_stopatvectors,
    AttrDict, closer, closerish, further, angle, similar_direction, shallow_angle,
)

DEFAULT_FONT='/usr/share/fonts/truetype/padauk/Padauk.ttf'
DEFAULT_GLYPH='u1021'

#==============
#This section is for functions that calculate and return a different data type
#==============

def calculate_parents(polyline_tuples):
    """This function takes a list of fontforge points and turns it into a list of dictionaries.
    Each dictionary has the polygon, the list of points, the children (the polygons inside the
    given polygon, and the parents (the polygons containing the given polygon).

    Input: a set of tuples: (point list, original FF contour)

    The reason for passing the original FF contour is because our dictionary data
    structure is going to need to hold a reference to it."""
    if polyline_tuples==[]:
        return []
    polygons=[]
    for line, orig_contour in polyline_tuples:
        d=dict()
        d['poly']=Polygon(ff_to_tuple(line))
        d['line']=line
        d['contour']=orig_contour
        d['children']=[]
        d['parents']=[]
        polygons.append(d)
    for a,b in itertools.permutations(polygons,2):
        if a['poly'].within(b['poly']):
            a['parents'].append(b)
            b['children'].append(a)
    return polygons

def levels(polygons):
    """This function takes a list of dictionaries from the parentsandchildren function
    and turns it into a list of lists of dictionaries. Each inner list is the list of
    the dictionaries corresponding to the polylines at the level of the index of the list."""
    maxdepth=-1
    for item in polygons:
        item['level']=len(item['parents'])
        maxdepth=max(maxdepth,item['level'])
    result=[]
    #result should go from 0 to maxdepth inclusive.
    for i in range(maxdepth+1):
        result.append([])
    for i in polygons:
        result[i['level']].append(i)
    return result


def calculateimmediateparent(levels):
    """This function takes a list of lists of dictionaries given by the levels function
    and adds the key "immediate parents" to each of the dictionaries, which gives the
    innermost polyline containing the given polyline"""
    for i, item in enumerate(levels[1:]):
        for polyline in item:
            for parent in polyline['parents']:
                if parent in levels[i]:
                    polyline['immediateparent']=parent
    return levels

def calculateimmediatechildren(levels):
    """This function takes a list of lists of dictionaries given by the levels function
    and adds the key "immediate children" to each of the dictionaries, which gives the
    outermost polyline inside the given polyline"""
    for i, item in enumerate(levels):
        if i==len(levels)-1:
            break
        for polyline in item:
            polyline['immediatechildren']=[]
            for child in polyline['children']:
                if child in levels[i+1]:
                    polyline['immediatechildren'].append(child)
    return levels

def extractbeziers(points):
    """This function takes a list of fontforge points and yields lists that contain single lines or beziers."""
    i=0
    while i<len(points)-1:
        # This appends a list of the two consecutive on-curve points with any off-curve points between them.
        if points[i+1].on_curve:
            added_bezier=points[i:i+2]
            i=i+1
        else:
            added_bezier=points[i:i+3]
            i=i+2
        yield added_bezier

#==============
#This section is for functions that do extra calculations
#==============

def extrapolate_midpoints(points, closecurve=True):
    """This function takes a list of fontforge points and if two consecutive points are off-curve
    it extrapolates the on-curve point between them. It will also, optionally, add
    the final point to the curve. (This is not always necessary.)"""
    if closecurve:
        if not (points[-1] == points[0]):
            points.append(points[0])  # Close the curve
    for a, b in pairwise(points):
        if a.on_curve or b.on_curve:
            # No need to extrapolate for this pair
            yield a
        else:
            midpoint = averagepoint_as_ffpoint(a, b)
            yield a
            yield midpoint
    # Last point will not have been part of any pairs, so it won't have been
    # yielded yet. E.g.
    yield points[-1]

def subdivideline(points,n):
    """This function takes a list of tuples or lists and finds n-1 evenly spaced points (tuples)
    along the line that connects them in between the two points"""
    if n<=0:
        raise ValueError("you cannot subdivide into less than one piece")
    if not type(n)==int:
        raise ValueError("you cannot subdivide into a non-integer number of pieces")
    i=0
    while i<=n:
        result1=(n-i)*points[0].x+i*points[1].x
        result2=(n-i)*points[0].y+i*points[1].y
        yield fontforge.point(result1/float(n),result2/float(n), True)
        i=i+1

def subdividebezier(points,n):
    """This function takes three fontforge points, and yields n-1 evenly spaced
    fontforge points along the bezier defined by those points"""
    if n<=0:
        raise ValueError("you cannot subdivide into less than one piece")
    if not type(n)==int:
        raise ValueError("you cannot subdivide into a non-integer number of pieces")
    i=0
    while i<=n:
        result1 = ((n-i)**2)*points[0].x + 2*i*(n-i)*points[1].x + i*i*points[2].x
        result2 = ((n-i)**2)*points[0].y + 2*i*(n-i)*points[1].y + i*i*points[2].y
        yield fontforge.point(result1/float(n*n),result2/float(n*n),True)
        i=i+1

def lowest(points):
    lowest=points[0]
    i=0
    while i<len(lowest):
        if lowest[1]>points[i][1]:
            lowest=points[i]
        i=i+1
    return (lowest, i)

def closesort3(point, points, epsilon=0.01):
    if len(points) == 0:
        return []
    def distance(otherpoint):
        return vectorlengthastuple(point, otherpoint)
    distances = map(distance, points)
    distances_with_points = list(zip(distances, points))
    distances_with_points.sort()
    if distances_with_points[0][0] < epsilon:
        # The target point was in the list; skip it
        print "Found myself in closesort3"
        del distances_with_points[0]
    return [point for distance, point in distances_with_points]

def twoclosestpoints(point, points, epsilon=0.01):
    closepoints = closesort3(point, points, epsilon)
    return closepoints[:2]

def closestpoint(point, points, epsilon=0.01):
    twopoints = twoclosestpoints(point, points, epsilon)
    if not twopoints:
        return None
    else:
        return twopoints[0]

"""Old algorithm for closestpoint was:
def closestpoint(point,points):
    closest=points[0]
    closestidx=0
    i=0
    while i<len(points):
        newclosest=closer(point,closest,points[i])
        if newclosest != closest:
            closestidx=i
        closest=newclosest
        i=i+1
    return (closest, closestidx)
"""

def closestpoint_in_same_direction(curpoint, oldpoint, points, epsilon=0.01):
    # Last line segment was oldpoint->curpoint. Find next point in general direction
    for candidate in closesort3(curpoint, points):
        if are_points_equal(candidate, oldpoint, epsilon):
            # Don't retrace our steps!
            continue
        # Keep going until we find one in the right direction
        if similar_direction(oldpoint, curpoint, candidate):
            return candidate
        else:
            continue
    # If we reach here, there were no more points in the right direction
    return None

def pointscloserthan(point,points,radius):
    closelist=[]
    for i in points:
        if are_points_equal(i, point):
            continue # Don't put points in their own neighbor list!
        if vectorlengthastuple(i,point)<=radius:
            closelist.append(i)
    return closelist

def closesort2(points):
    prevpoint,previdx=lowest(points)
    point,idx=closestpoint(prevpoint,points)
    sortedpoints=[prevpoint,point]
    del points[previdx]
    if idx==previdx:
        pass
    elif idx>previdx:
        try:
            del points[idx-1]
        except IndexError:
            print "Failed to remove index {} from list of length {}".format(idx-1, len(points))
            raise
    else:
        del points[idx]
    k=0
    numberofpoints=len(points)
    while k<numberofpoints:
        nextpointapproximatelocation=(2*point[0]-prevpoint[0],2*point[1]-prevpoint[1])
        closest,closestidx=closestpoint(nextpointapproximatelocation,points)
        sortedpoints.append(closest)
        prevpoint, point = point, closest
        try:
            del points[closestidx]
        except IndexError:
            pass
        k=k+1
    return sortedpoints

def closesort(points,length):
    lowpoint,idx=lowest(points)
    sortedpoints=[lowpoint]
    del points[idx]
    k=0
    numberofpoints=len(points)
    closest=lowpoint
    while k<numberofpoints:
        closestnew=closestpoint(closest,points)
        closest,closestidx=closestnew
        sortedpoints.append(closest)
        del points[closestidx]
        k=k+1
    return sortedpoints

def points_to_all_lines(points,length):
    lines=[]
    print len(points)
    while points!=[]:
        point=points[0]
        del points[0]
        closepoints=pointscloserthan(point,points,length)
        #i=0
        #while i<len(closepoints):
        #    j=i+1
        #    while j<len(closepoints):
        #        if closer(closepoints[i],point,closepoints[j])==closepoints[j]:
        #            extra=further(point,closepoints[i],closepoints[j])
        #            if len(closepoints)>1:
        #                closepoints.remove(extra)
        #        j=j+1
        #    i=i+1
        for i in closepoints:
            lines.append([point,i])
        if closepoints:
            points.remove(closepoints[0])
            points=[closepoints[0]]+points
    return lines

def find_neighbors(points, stroke_width):
    neighbors = {}
    for point in points:
        neighborlist = pointscloserthan(point, points, stroke_width)
        neighbors[point] = neighborlist
    return neighbors

def is_within(line, polygon):
    if isinstance(line, LineString):
        pass
    else:
        line = any_to_linestring(line)
    if isinstance(polygon, Polygon):
        pass
    else:
        polygon = any_to_polygon(polygon, [])
    return line.difference(polygon).is_empty

def iscloseto(v, outline):
    """Returns true if vector v is almost identical to any vector in the outline.
    Outline format expected: polyline"""
    #print "iscloseto({}, {})".format(v, outline)
    return any(are_lines_equal(v, test, epsilon=1.0) for test in pairwise(outline))

def filtertriangles(triangles, outlines):
    """Remove all triangle edges that coincide with any edge of the outline or any holes
    Note that the "outlines" parameter should be a list of the outside polyline and the holes."""
    # Convert triangles to list of 3-element lists of 2-tuples
    # E.g., [[(p1,p2),(p2,p3),(p3,p1)], [(p4,p5),(p5,p6),(p6,p4)], ...]
    def isvalid(line):
        #print "isvalid({})".format(line)
        if any(iscloseto(line, outline) for outline in outlines):
            m = averagepoint_as_tuple(line[0], line[1])
            #draw_fat_point(args.screen, m, args.em, args.zoom, red)
        return not any(iscloseto(line, outline) for outline in outlines)
    #if len(triangles) <= 2000:
    if False:
        print "DEBUG: triangles before filtering:"
        import pprint
        pprint.pprint(triangles)
        print "DEBUG: outlines before filtering"
        pprint.pprint(outlines)
        print "DEBUG: triangles after filtering:"
        pprint.pprint(list(iterfilter_stopatvectors(isvalid, triangles)))
    return iterfilter_stopatvectors(isvalid, triangles)

#================
#This section is for functions that actually do things beyond calculations and converting between data types
#================

def extractvectors(points, minlength=None):
    """Note: points argument should be a list (or generator) of FF points.
    minlength argument is minimum length that each subdivision should be. If
    not specified, default will be to not subdivide straight lines, and to
    subdivide Bezier curves until the angle change of each segment is less
    than N degrees, where N is currently 3 but might change in the future."""
    points = list(points)
    for candidate in extractbeziers(points):
        if len(candidate) == 2:
            # It's a vector
            if minlength is None:
                subdivision = 1
            else:
                segmentlength = float(vectorlength(candidate[-1],candidate[0]))
                subdivision=int(math.floor(segmentlength / minlength))
                subdivision=max(subdivision,1) # Should be at least 1
            subdivided=list(subdivideline(candidate,subdivision))
            #subdivided=list(subdivideline(candidate,1))
        else:
            # It's a Bezier curve
            if minlength is None:
                subdivision = find_shallow_subdivision(candidate)
                #subdivision = 1
            else:
                segmentlength = float(vectorlength(candidate[-1],candidate[0]))
                subdivision=int(math.floor(segmentlength / minlength))
                subdivision=max(subdivision,1) # Should be at least 1
            subdivided=list(subdividebezier(candidate,subdivision))
        for v in pairwise(subdivided):
            yield v

def find_shallow_subdivision(bezier, tolerance=3):
    # Subdivide a Bezier curve into enough segments (min 3, max 25) to form
    # angles of less than 5 degrees.
    for n in range(3, 26, 2):
        subdivided = list(subdividebezier(bezier, n))
        similar = all(shallow_angle(a,b,c, tolerance) for a, b, c in by_threes(subdivided))
        if similar:
            #print "{} was enough".format(n)
            break
        else:
            #print "{} was not enough".format(n)
            continue
    return n

def calculate_width(polydata, fudgefactor=0.05):
    polyline = polydata['line']
    children = polydata.get('immediatechildren', [])
    holes = [item['line'] for item in children]
    approx_polygon = Polygon(polyline, holes)
    width = 2 * approx_polygon.area / approx_polygon.length
    # Add a fudge factor (default 5%)
    multiplier = 1.0 + fudgefactor
    width = width * multiplier

    # Now recalculate the polyline and polygon based on the calculated width
    # Ensure width is within the bounds set at the command line
    width = max(width, args.minstrokewidth)
    width = min(width, args.maxstrokewidth)
    polydata['width'] = width
    print width
    return width

def recalculate_polys(polydata):
        width = polydata['width']
        holes = polydata.get('immediatechildren', [])
        for hole_data in holes:
            hole_contour = list(extrapolate_midpoints(list(hole_data['contour'])))
            hole_vectors = extractvectors(hole_contour, width)
            hole_data['line'] = vectorpairs_to_pointlist(hole_vectors)
            hole_data['poly'] = any_to_polygon(hole_data['line'], [])
        real_contour = list(extrapolate_midpoints(list(polydata['contour'])))
        real_vectors = extractvectors(real_contour, width)
        real_hole_contours = [data['contour'] for data in holes]
        real_polyline = vectorpairs_to_pointlist(real_vectors)

        polydata['line'] = real_polyline
        polydata['poly'] = any_to_polygon(real_polyline, real_hole_contours)

def saferemove(item, list):
    """Remove an item from a list, ignoring errors if it wasn't there"""
    try:
        list.remove(item)
    except ValueError:
        pass

def calculate_midlines(midpoints, bounding_polygon):
    triangles = collections.defaultdict(list)  # Keys are midpoints
    singles = []
    doubles = []
    triples = []
    # Note that "triangles" is a bit of a misnomer, as we have replaced each
    # side of the triangle with its midpoint -- and then eliminated the lines
    # that coincide with the outline. Now, if a "triangle" still has three
    # "sides" (points), it marks an intersection. If it has two sides, it's
    # the middle of a line (and easy to resolve). If it has one side, it's
    # an endpoint.

    # Structure of midpoints list:
    # [t1, t2, t3, ..., tn] where t looks like [m1, m2, m3] (or 2 or 1 points)
    # and where each m looks like (x,y)
    for tri in midpoints:
        for m in tri:
            triangles[m].append(tri)
        # Instead of "if len(tri) == 1: singles.append(tri)", etc., we can do:
        [[], singles, doubles, triples][len(tri)].append(tri)
    debug('{} endpoints found', len(singles))
    debug('{} ', singles)
    debug('{} midpoints found', len(doubles))
    debug('{} tripoints found', len(triples))
    debug('{} ', triples)

    current_line = []  # Will be a list of vectors (pairs of points)
    drawn_lines = []  # Will be a list of lists of vectors (pairs of points)
    connected_points = collections.defaultdict(list)  # Keys are midpoints
    finished_points = []  # Will we use this?

    # As we draw each line segment between two midpoints, we will:
    # 1) Add the segment to the current_line list (appending it)
    # 2) connected_points[a].append(b)
    #    connected_points[b].append(a)
    def record_drawn_line(p1, p2):
        # Record a drawn line between p1 and p2
        current_line.append([p1, p2])
        connected_points[p1].append(p2)
        connected_points[p2].append(p1)
    # NOTE: It's possible that we'll discover we want some other data structure
    # for our line segments. Find out.

    def done():
        numpoints = len(singles)+len(doubles)+len(triples)
        return len(connected_points) == numpoints

    def first_not_in(a, b, default=None):
        """Returns the first item from collection a not found in collection b.
        Collection a is a collection of collections (like "singles" and "triples" above),
        and b must support "if item in b" lookup."""
        for coll in a:
            for item in coll:
                if item in b:
                    continue
                return item
        return default

    def get_other_point(coll, p, default=None):
        """Given a collection of points, return the first point that is not p."""
        for candidate in coll:
            if are_points_equal(candidate, p):
                continue
            return candidate
        return None

    def next_point(cur_point):
        debug('next_point({}) called with connected points: {}', cur_point, connected_points)
        old_point = get_other_point(connected_points[cur_point], cur_point)
        # All midpoints are part of two triangles. If only one of those has
        # two valid sides (two remaining points), draw to it. If there are
        # two with two valid sides, pick one arbitrarily.
        tris = filter(lambda coll: len(coll) == 2, triangles[cur_point])
        if len(tris) == 2:
            next_tri = (tris[1] if old_point in tris[0] else tris[0])
        elif len(tris) == 1:
            next_tri = tris[0]
        else:
            # No next point to find
            return None
        return get_other_point(next_tri, cur_point)

    def arity(point):
        """How many connections is this point part of?"""
        t = triangles[point]
        return max(*map(len, t))

    exit_now = False
    while not done() and not exit_now:
        curpt = first_not_in(singles, finished_points)
        if curpt is None:
            break
        nextpt = next_point(curpt)
        if nextpt in finished_points:
            break
        while nextpt is not None:
            record_drawn_line(curpt, nextpt)
            finished_points.append(curpt) # TODO: Check arity of curpt first: if 3, not yet finished... I suppose
            #prevpt = curpt  # Needed? FIXME: Remove if not needed
            curpt = nextpt
            nextpt = next_point(curpt)
            if nextpt in finished_points:
                break
        drawn_lines.append(current_line)
        current_line = []

    exit_now = False
    while not done() and not exit_now:
        curpt = first_not_in(triples, finished_points)
        if curpt is None:
            break
        nextpt = next_point(curpt)
        if nextpt in finished_points:
            finished_points.append(curpt)
            continue
        while nextpt is not None:
            record_drawn_line(curpt, nextpt)
            finished_points.append(curpt) # TODO: Check arity of curpt first: if 3, not yet finished... I suppose
            #prevpt = curpt  # Needed? FIXME: Remove if not needed
            curpt = nextpt
            nextpt = next_point(curpt)
            if nextpt in finished_points:
                break
        drawn_lines.append(current_line)
        current_line = []

    return drawn_lines

def extraction_demo(fname,letter):
    font = fontforge.open(fname)
    global args
    args.em = font.em
    if isinstance(letter, int):
        codepoint = letter
    elif letter.startswith('U+'):
        codepoint = int(letter[2:], 16)
    else:
        codepoint = letter
    glyph = font[codepoint]
    layer = glyph.foreground
    print "{} has {} layer{}".format(args.glyphname, len(layer), ('' if len(layer) == 1 else 's'))
    polylines = []
    polylines_to_draw = []
    alltriangles = []
    allmidpoints = []
    allmidlines = []
    # Calculate stroke width by first extracting vectors with no subdivision;
    # then convert to a Shapely polygon and calculate stroke width via the
    # 2*area / length algorithm. Then re-extract vectors with the real
    # stroke length.
    calculated_stroke_width = 0
    # Extract vectors with the real stroke width now
    approx_outlines = []
    for contour in layer:
        points = extrapolate_midpoints(list(contour))
        approx_vectors = extractvectors(points)
        linestring = vectorpairs_to_linestring(approx_vectors)
        approx_outlines.append((linestring, contour))
    approx_parent_data = calculate_parents(approx_outlines)
    approx_level_data = levels(approx_parent_data)
    approx_level_data = calculateimmediatechildren(approx_level_data)
    screen = setup_screen()
    args.screen = screen
    for level in approx_level_data[::2]:
        for polydata in level:
            width = calculate_width(polydata)

            # Recalculate the data['poly'] and data['line'] shapes,
            # subdividing Beziers and vectors based on calculated width
            recalculate_polys(polydata)

            real_polyline = polydata['line']
            real_polygon = polydata['poly']
            polylines_to_draw.append(any_to_linestring(real_polyline))
            children = polydata.get('immediatechildren', [])
            triangles = make_triangles(polydata, children)
            alltriangles.extend(triangles)
            trianglelines = map(triangle2lines, triangles)
            outside_polyline = any_to_polyline(real_polyline)
            outside_polyline.append(outside_polyline[0])  # Close it
            for line in pairwise(outside_polyline):
                #print line
                m = averagepoint_as_tuple(line[0], line[1])
                #draw_fat_point(args.screen, m, args.em, args.zoom, red)
            holes = map(any_to_closedpolyline, [child['line'] for child in children])
            bounding_polygon = any_to_polygon(outside_polyline, holes)
            for hole in holes:
                for line in pairwise(hole):
                    m = averagepoint_as_tuple(line[0], line[1])
                    #draw_fat_point(args.screen, m, args.em, args.zoom, red)
                polylines_to_draw.append(hole)
            outlines_to_filter = [outside_polyline] + holes
            real_trianglelines = list(filtertriangles(trianglelines, outlines_to_filter))
            midpoints = list(itermap_stopatvectors(averagepoint_as_tuplevector, real_trianglelines))
            midlines = list(calculate_midlines(midpoints, bounding_polygon))
            debug('Calculated midlines: {}', midlines)
            # Structure of midpoints now:
            # [t1, t2, t3] where t1,t2,t3 are: [m1, m2, m3] or [m1, m2] or [m1]
            # And m1, m2, m3 are (x,y)
            # Basically, each triangle's vectors have been changed to midpoints,
            # but the structure still remains
            #print len(midpoints), 'midpoints found'
            #debug(midpoints)
            for t in midpoints:
                if len(t) == 1:
                    #debug("Identified endpoint:")
                    for m in t:
                        #debug(m)
                        draw_fat_point(screen, m, args.em, args.zoom, green)
            allmidpoints.extend(midpoints)
            allmidlines.extend(map(vectorpairs_to_pointlist, midlines))
            debug('All midlines so far: {}', allmidlines)

            # Step 1: Find neighbors (points within distance X, about half the stroke width)
            """ Comment out this block -- we're redoing it with triangle-based algorithm
            neighbor_distance = width * 1.5
            all_neighbors = find_neighbors(midpoints, neighbor_distance)

            # Step 2: Any points with all neighbors in the "same direction" are endpoints
            # Note that "same direction" is a fuzzy concept: how wide of an arc needs
            # to contain all the neighbors before they count as "same direction"?
            # 60 degrees? 120 degrees? After all, several of its neighbors may
            # be along a curve...
            def is_endpoint(point, neighborlist):
                if len(neighborlist) == 1:
                    return True
                return all(similar_direction(point, a, b, 60) for a, b in pairwise(neighborlist))
            endpoints = [point for (point, neighbors) in all_neighbors.items() if is_endpoint(point, neighbors)]
            for p in endpoints:
                debug('Endpoint: {}', p)
                draw_fat_point(screen, p, args.em, args.zoom, green)
                pass
            #print "Identified endpoints:"
            #print endpoints

            # Calculate the midlines, then append them
            midlines = vectorpairs_to_pointlist(calculate_midlines(midpoints, endpoints, bounding_polygon))
            print "Calculated these midlines:"
            for m in midlines:
                print m
            allmidlines.append(midlines)
            """
            #break  # Uncomment this to draw only the first "world"

    draw_all(screen, polylines_to_draw, [], alltriangles, emsize=args.em, zoom=args.zoom, polylinecolor=blue, trianglecolor=red)
    #draw_midlines(screen,[],midpoints)
    #lines=points_to_all_lines(midpoints, width*1.2)
    #draw_midlines(screen, lines, midpoints, polylinecolor=green)
    draw_midlines(screen, allmidlines, midpoints, emsize=args.em, zoom=args.zoom, polylinecolor=green)
    wait_for_keypress(args.em, args.zoom)
    return points

def make_triangles(polygon_data, holes=None):
    """This function takes a dictionary, and an optional holes parameter
    that determines the holes of a polyline, and tesselates the polyline
    into triangles. This is an intermediate step to calculating the midpoints"""
    if holes is None:
        holes = []
    triangles = []
    new_polyline = convert_polyline_to_polytri_version(polygon_data['line'])
    if are_points_equal(new_polyline[-1], new_polyline[0]):
        del new_polyline[-1]
    cdt = p2t.CDT(new_polyline)
    for hole_data in holes:
        hole = hole_data['line']
        if hasattr(hole, 'coords'):
            hole = list(hole.coords)
        if are_points_equal(hole[-1], hole[0]):
            del hole[-1]
        hole = convert_polyline_to_polytri_version(hole)
        cdt.add_hole(hole)
    triangles.extend(cdt.triangulate())
    return triangles

def get_glyph(fname, letter):
    font = fontforge.open(fname)
    if isinstance(letter, int):
        codepoint = letter
    elif letter.startswith('U+'):
        codepoint = int(letter[2:], 16)
    else:
        codepoint = letter
    glyph = font[codepoint]
    return glyph

def find_straight_lines(ffcontour):
    for a, b in pairwise(ffcontour):
        if a.on_curve and b.on_curve:
            yield a, b
    try:
        ffcontour[0]
    except IndexError:
        # Can't check first & last point, so just give up
        return
    else:
        if ffcontour[0].on_curve and ffcontour[-1].on_curve:
            yield ffcontour[-1], ffcontour[0]

def estimate_strokewidth(ffcontour):
    pass

DEBUG=False
def debug(s, *args, **kwargs):
    if not DEBUG:
        return
    if not args and not kwargs:
        print s
    else:
        print s.format(*args, **kwargs)

def new_extraction_method(fontfilename, lettername):
    glyph = get_glyph(fontfilename, lettername)
    emsize = glyph.font.em
    debug("Glyph {} has em size {}", glyph.glyphname, emsize)
    # Data formats we'll use:
    # 1) Lists of Fontforge points forming a closed outline. The lists are not closed. These are "ffoutlines".
    # 2) Lists of (x,y) tuples (x and y are floats) forming a closed outline. The lists are not closed. These are "polylines".
    data = AttrDict()
    data.outlines = []
    for contour in glyph.foreground:
        debug("This {}clockwise contour has {} points:", ('' if contour.isClockwise() else 'counter-'), len(contour))
        #debug(contour)
        outline = AttrDict()
        outline.contour = contour
        # Many contours will have two or more off-curve points in a row. The
        # TrueType spec allows for this; the implied on-curve point is the point
        # precisely between the two off-curve points. extrapolate_midpoints() will
        # give us an outline with on-curve points in the right places.
        outline.complete_contour = list(extrapolate_midpoints(list(contour), False))
        # Now we should work out the stroke width of the contour. First find any straight lines...
        strokewidth = 1e999
        for a, b in find_straight_lines(outline.complete_contour):
            debug("Found a straight line: {}", (a,b))
            distance = vectorlength(a,b)
            strokewidth = min(distance, strokewidth)
        if strokewidth < 1e999:
            debug("Found stroke width of {}", strokewidth)
        else:
            debug("Couldn't find stroke width")
        outline.polyline = any_to_polyline(outline.complete_contour)
        outline.linestring = any_to_linestring(outline.complete_contour)
        data.outlines.append(outline)

        #debug(list(outline.linestring.coords))

def parse_args():
    "Parse the arguments the user passed in"
    parser = argparse.ArgumentParser(description="Demonstrate parsing arguments")
    #parser.add_argument('--help', help="Print the help string")
    parser.add_argument('-v', '--verbose', action="store_true", help="Give more verbose error messages")
    parser.add_argument("inputfilename", nargs="?", default=DEFAULT_FONT, help="Font file (SFD or TTF format)")
    parser.add_argument("glyphname", nargs="?", default=DEFAULT_GLYPH, help="Glyph name to extract")
    parser.add_argument('-z', '--zoom', action="store", type=float, default=1.0, help="Zoom level (default 1.0)")
    parser.add_argument('-m', '--minstrokewidth', action="store", type=float, default=1, help="The minimum stroke width")
    parser.add_argument('-M', '--maxstrokewidth', action="store", type=float, default=1e100, help="The maximum stroke width")
    args = parser.parse_args()
    args.svgfilename = args.glyphname + '.svg'
    args.datfilename = args.glyphname + '.dat'
    return args

def main():
    """This is the main function we use that calls extraction_demo and also runs
    a sanity check to make sure everything works properly."""
    global args
    args = parse_args()
    #new_extraction_method(args.inputfilename, args.glyphname)
    extraction_demo(args.inputfilename, args.glyphname)
    return 0

if __name__ == "__main__":
    retcode=main()
    if retcode!=0:
        sys.exit(retcode)

#    if not os.path.exists(opts.inputfilenamappend(e):
#        print "File {} not found or not accessible".format(opts.inputfilename)
#        sys.exit(2)
#    font = fontforge.open(opts.inputfilename)
#    font[opts.glyphname].export(opts.exportname)
#    font.close()
