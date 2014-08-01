#!/usr/bin/env python

from __future__ import division

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
import shutil
import textwrap
from shapely.geometry import Polygon, LineString, Point

from dataconvert import import_p2t
p2t = import_p2t()

from dataconvert import (
    any_to_linestring, any_to_polygon, any_to_polyline, any_to_closedpolyline,
    convert_polyline_to_polytri_version,
    triangle2lines, vectorpairs_to_pointlist, vectorpairs_to_linestring,
)
from generalfuncs import (
    pairwise, by_threes, flatten,
    vectorlength, are_points_equal, are_lines_equal,
    averagepoint_as_ffpoint, averagepoint_as_tuple, averagepoint_as_tuplevector,
    comp, iterfilter_stopatvectors, itermap_stopatvectors,
    AttrDict, closer, closerish, further, angle, similar_direction, shallow_angle,
    center_of_triangle, circle_at,
)

# ==============
# This section is for functions that calculate and return a different data type
# ==============

def calculate_parents(polyline_tuples):
    """This function takes a list of fontforge points and turns it into a list of dictionaries.
    Each dictionary has the polygon, the list of points, the children (the polygons inside the
    given polygon, and the parents (the polygons containing the given polygon).

    Input: a set of tuples: (point list, original FF contour)

    The reason for passing the original FF contour is because our dictionary data
    structure is going to need to hold a reference to it."""
    if polyline_tuples == []:
        return []
    polygons = []
    for line, orig_contour in polyline_tuples:
        d = dict()
        d['poly'] = Polygon(line)
        d['line'] = line
        d['contour'] = orig_contour
        d['children'] = []
        d['parents'] = []
        polygons.append(d)
    for a, b in itertools.permutations(polygons, 2):
        if a['poly'].within(b['poly']):
            a['parents'].append(b)
            b['children'].append(a)
    return polygons

def levels(polygons):
    """This function takes a list of dictionaries from the parentsandchildren function
    and turns it into a list of lists of dictionaries. Each inner list is the list of
    the dictionaries corresponding to the polylines at the level of the index of the list."""
    maxdepth = -1
    for item in polygons:
        item['level'] = len(item['parents'])
        maxdepth = max(maxdepth, item['level'])
    result = []
    # result should go from 0 to maxdepth inclusive.
    for i in range(maxdepth + 1):
        result.append([])
    for i in polygons:
        result[i['level']].append(i)
    return result


def calculate_immediate_parent(levels):
    """This function takes a list of lists of dictionaries given by the levels function
    and adds the key "immediate parents" to each of the dictionaries, which gives the
    innermost polyline containing the given polyline"""
    for i, item in enumerate(levels[1:]):
        for polyline in item:
            for parent in polyline['parents']:
                if parent in levels[i]:
                    polyline['immediateparent'] = parent
    return levels

def calculate_immediate_children(levels):
    """This function takes a list of lists of dictionaries given by the levels function
    and adds the key "immediate children" to each of the dictionaries, which gives the
    outermost polyline inside the given polyline"""
    for i, item in enumerate(levels):
        if i == len(levels)-1:
            break
        for polyline in item:
            polyline['immediatechildren'] = []
            for child in polyline['children']:
                if child in levels[i+1]:
                    polyline['immediatechildren'].append(child)
    return levels

def extract_beziers(points):
    """This function takes a list of fontforge points and yields lists that contain single lines or beziers."""
    i = 0
    while i<len(points)-1:
        # This appends a list of the two consecutive on-curve points with any off-curve points between them.
        if points[i+1].on_curve:
            added_bezier = points[i:i+2]
            i += 1
        else:
            added_bezier = points[i:i+3]
            i += 2
        yield added_bezier

# ==============
# This section is for functions that do extra calculations
# ==============

def extrapolate_midpoints(points, closecurve = True):
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

def subdivideline(points, n):
    """This function takes a list of tuples or lists and finds n-1 evenly spaced points (tuples)
    along the line that connects them in between the two points"""
    if n <= 0:
        raise ValueError("you cannot subdivide into less than one piece")
    if not type(n) == int:
        raise ValueError("you cannot subdivide into a non-integer number of pieces")
    i = 0
    while i <= n:
        result1 = (n-i)*points[0].x + i*points[1].x
        result2 = (n-i)*points[0].y + i*points[1].y
        yield fontforge.point(result1/float(n), result2/float(n), True)
        i += 1

def subdividebezier(points, n):
    """This function takes three fontforge points, and yields n-1 evenly spaced
    fontforge points along the bezier defined by those points"""
    if n <= 0:
        raise ValueError("you cannot subdivide into less than one piece")
    if not type(n) == int:
        raise ValueError("you cannot subdivide into a non-integer number of pieces")
    i = 0
    while i <= n:
        result1 = ((n-i)**2)*points[0].x + 2*i*(n-i)*points[1].x + i*i*points[2].x
        result2 = ((n-i)**2)*points[0].y + 2*i*(n-i)*points[1].y + i*i*points[2].y
        yield fontforge.point(result1/float(n*n), result2/float(n*n), True)
        i += 1

def iscloseto(v, outline):
    """Returns true if vector v is almost identical to any vector in the outline.
    Outline format expected: polyline"""
    return any(are_lines_equal(v, test, epsilon = 1.0) for test in pairwise(outline))

def filtertriangles(triangles, outlines):
    """Remove all triangle edges that coincide with any edge of the outline or any holes
    Note that the "outlines" parameter should be a list of the outside polyline and the holes."""
    # Convert triangles to list of 3-element lists of 2-tuples
    # E.g., [[(p1,p2), (p2,p3), (p3,p1)], [(p4,p5), (p5,p6), (p6,p4)], ...]
    def isvalid(line):
        if any(iscloseto(line, outline) for outline in outlines):
            m = averagepoint_as_tuple(line[0], line[1])
        return not any(iscloseto(line, outline) for outline in outlines)
    return iterfilter_stopatvectors(isvalid, triangles)

# ================
# This section is for functions that actually do things beyond calculations and converting between data types
# ================

def extract_vectors(points, minlength = None):
    """Note: points argument should be a list (or generator) of FF points.
    minlength argument is minimum length that each subdivision should be. If
    not specified, default will be to not subdivide straight lines, and to
    subdivide Bezier curves until the angle change of each segment is less
    than N degrees, where N is currently 3 but might change in the future."""
    points = list(points)
    for candidate in extract_beziers(points):
        if len(candidate) == 2:
            # It's a vector
            if minlength is None:
                subdivision = 1
            else:
                segmentlength = float(vectorlength(candidate[-1], candidate[0]))
                subdivision = int(math.floor(segmentlength / minlength))
                subdivision = max(subdivision, 1) # Should be at least 1
            subdivided = list(subdivideline(candidate, subdivision))
            #subdivided = list(subdivideline(candidate, 1))
        else:
            # It's a Bezier curve
            if minlength is None:
                subdivision = find_shallow_subdivision(candidate)
                #subdivision = 1
            else:
                segmentlength = float(vectorlength(candidate[-1], candidate[0]))
                subdivision = int(math.floor(segmentlength / minlength))
                subdivision = max(subdivision, 1) # Should be at least 1
            subdivided = list(subdividebezier(candidate, subdivision))
        for v in pairwise(subdivided):
            yield v

def find_shallow_subdivision(bezier, tolerance = 3):
    # Subdivide a Bezier curve into enough segments (min 3, max 25) to form
    # angles of less than 5 degrees.
    for n in range(3, 26, 2):
        subdivided = list(subdividebezier(bezier, n))
        similar = all(shallow_angle(a, b, c, tolerance) for a, b, c in by_threes(subdivided))
        if similar:
            break
        else:
            continue
    return n

def calculate_width(polydata, fudgefactor = 0.05):
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
    return width

def recalculate_polys(polydata):
        width = polydata['width']
        holes = polydata.get('immediatechildren', [])
        for hole_data in holes:
            hole_contour = list(extrapolate_midpoints(list(hole_data['contour'])))
            hole_vectors = extract_vectors(hole_contour, width)
            hole_data['line'] = vectorpairs_to_pointlist(hole_vectors)
            hole_data['poly'] = any_to_polygon(hole_data['line'], [])
        real_contour = list(extrapolate_midpoints(list(polydata['contour'])))
        real_vectors = extract_vectors(real_contour, width)
        real_hole_contours = [data['contour'] for data in holes]
        real_polyline = vectorpairs_to_pointlist(real_vectors)

        polydata['line'] = real_polyline
        polydata['poly'] = any_to_polygon(real_polyline, real_hole_contours)

def calculate_midlines(midpoints):
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
    # and where each m looks like (x, y)
    for tri in midpoints:
        for m in tri:
            triangles[m].append(tri)
        # Instead of "if len(tri) == 1: singles.append(tri)", etc., we can do:
        [[], singles, doubles, triples][len(tri)].append(tri)

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
        numpoints = len(singles) + len(doubles) + len(triples)
        return len(connected_points) == numpoints

    def first_not_in(a, b, default = None):
        """Returns the first item from collection a not found in collection b.
        Collection a is a collection of collections (like "singles" and "triples" above),
        and b must support "if item in b" lookup."""
        for coll in a:
            for item in coll:
                if item in b:
                    continue
                return item
        return default

    def get_other_point(coll, p, default = None):
        """Given a collection of points, return the first point that is not p."""
        for candidate in coll:
            if are_points_equal(candidate, p):
                continue
            return candidate
        return None

    def next_point(cur_point):
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
        """How many connections is this point part of? In other words, how
        many other points are on the triangles this point belongs to?
        """
        # To get a perfectly accurate count:
        #   1) Flatten the list of triangles
        #   2) Filter out the current point
        #   3) Return the count of the remainder
        t = triangles[point]
        otherpoints = filter(lambda x: x != point, flatten(t))
        return len(otherpoints)

    def find_centerpoint(edgepoint):
        """Given a single point on one side of a triangle, find the center
        point of the triangle."""
        # Find the intersection triangle (the one with three sides remaining)
        tris = [t for t in triangles[edgepoint] if len(t) == 3]
        if len(tris) < 1:
            return None
        elif len(tris) > 1:
            # If we're right between two intersection triangles, this point
            # that's right between them is the center of the polygon formed
            # by adding them both together.
            return edgepoint
        else:
            t = tris[0]
        # Special case: if ANY point in t has arity 4, then we should use that
        # point (the place where two intersection triangles touch), rather than
        # the center of *this* triangle, as our "centerpoint"
        for p in t:
            if arity(p) == 4:
                return p
        centerpoint = center_of_triangle(t)
        return centerpoint

    exit_now = False
    while not done() and not exit_now:
        curpt = first_not_in(singles, finished_points)
        if curpt is None:
            break
        ac = arity(curpt)
        nextpt = next_point(curpt)
        if nextpt is None or nextpt in finished_points:
            break
        while nextpt is not None:
            record_drawn_line(curpt, nextpt)
            an = arity(nextpt)
            if an > 2:
                # This is part of a triangle: cancel the line just drawn and
                # draw to centerpoint of triangle instead. However, leave the
                # connected_points dict (which record_drawn_line has updated)
                # alone.
                del current_line[-1]
                center = find_centerpoint(nextpt)
                current_line.append([curpt, center])
            if ac > 2:
                # TODO: Check that all this point's neighbors are finished; iff so, add this point to finished_points
                finished_points.append(curpt)
            else:
                finished_points.append(curpt)
            curpt = nextpt
            ac = arity(curpt)
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
        ac = arity(curpt)
        nextpt = next_point(curpt)
        if nextpt is None or nextpt in finished_points:
            finished_points.append(curpt)
            continue
        # Now because the current point was the side of a triangle, we want
        # to draw the line from the centroid, not from the current point. We
        # set curpt to the center here rather than earlier, because we needed
        # it earlier in the next_point(curpt) call.
        start_from = find_centerpoint(curpt)
        if start_from is None:
            print "find_centerpoint({}) failed...".format(curpt)
            start_from = curpt
            edit_line_after_recording = False
        else:
            edit_line_after_recording = True
        while nextpt is not None:
            record_drawn_line(curpt, nextpt)
            an = arity(nextpt)
            if an > 2:
                # This is part of a triangle: cancel the line just drawn and
                # draw to centerpoint of triangle instead. However, leave the
                # connected_points dict (which record_drawn_line has updated)
                # alone.
                end_at = find_centerpoint(nextpt)
                edit_line_after_recording = True
            else:
                end_at = nextpt
                # Leave edit_line_after_recording unchanged
            if edit_line_after_recording:
                del current_line[-1]
                current_line.append([start_from, end_at])
                edit_line_after_recording = False
            if ac > 2:
                # TODO: Check that all this point's neighbors are finished; iff so, add this point to finished_points
                finished_points.append(curpt)
            else:
                finished_points.append(curpt)
            curpt = nextpt
            start_from = curpt
            ac = arity(curpt)
            nextpt = next_point(curpt)
            if nextpt in finished_points:
                break
        drawn_lines.append(current_line)
        current_line = []

    # One more thing we need to do: any 4-arity points need to have a line
    # drawn between both of their centerpoints. See U+aa76 in Padauk font for
    # a visual example of why. (The small loop near the bottom).

    return drawn_lines

def calculate_dots(midlines, radius, spacing):
    # Radius is in em units, same as the midlines lengths; spacing is given as
    # a multiple of radius.
    unit_spacing = spacing * radius
    linestrings = []
    # Midlines is in the format [line1, line2, line3] and each line (polyline
    # really) is in the format [[p1,p2], [p2,p3], [p3,p4]..., [p(n-1),pn]]. We
    # want to use shapely.LineString objects, whose constructor wants the
    # format [p1, p2, p3, ..., pn].
    for line in midlines:
        linestrings.append(any_to_linestring(vectorpairs_to_pointlist(line)))
    dots = []
    for line in linestrings:
        numdots = math.floor(line.length / float(unit_spacing))
        if numdots < 1.0:
            numdots = 1.0
        line_spacing = line.length / float(numdots)
        distance = 0.0
        while distance <= line.length:
            dot = line.interpolate(distance)
            #dot = line.interpolate(distance).buffer(radius)
            dots.append(dot)
            distance += line_spacing
    return dots

def silent_fontopen(fname):
    # Fontforge opens fonts in C code, so we can't redirect Python's sys.stderr
    # to /dev/null and hope that that will work. We need to redirect the
    # OS-level file descriptor for stderr (2) to /dev/null instead.
    # Method from http://stackoverflow.com/a/8805144/2314532
    origstderr = os.dup(2)
    devnull = os.open('/dev/null', os.O_WRONLY)
    os.dup2(devnull, 2)
    fontobj = fontforge.open(fname)
    os.dup2(origstderr, 2)
    os.close(devnull)
    os.close(origstderr)
    return fontobj

def create_dotted_font(fname):
    input_font = silent_fontopen(fname)
    global args
    args.em = input_font.em
    shutil.copy2(fname, args.output)
    new_font = silent_fontopen(args.output)
    for glyphname in input_font:
        if glyphname in ('.notdef', '.null'): continue
        glyph = input_font[glyphname]
        new_glyph = new_font[glyphname]
        new_glyph.clear()
        print "Processing glyph at codepoint U+{:04X} named {}".format(glyph.encoding, glyphname)
        glyph.unlinkRef()
        copy_glyph(glyph, new_glyph)
    font_type = args.output.lower().rsplit('.', 1)[-1]
    if font_type == 'sfd':
        new_font.save(args.output)
    else:
        new_font.generate(args.output)
    print "Dotted font created as", args.output
    if args.visualize:
        print "Press any key to exit"
        import visualization
        visualization.wait_for_keypress(args.em, args.zoom)

def extraction_demo(fname, letter):
    font = silent_fontopen(fname)
    global args
    args.em = font.em
    if isinstance(letter, int):
        codepoint = letter
    elif letter.startswith('U+'):
        codepoint = int(letter[2:], 16)
    else:
        codepoint = letter
    glyph = font[codepoint]
    glyph.unlinkRef()
    dots = extract_dots(glyph, args.visualize)
    print "{} dots found".format(len(dots))
    if args.visualize:
        import visualization
        visualization.wait_for_keypress(args.em, args.zoom)

def extract_dots(glyph, show_glyph=True):
    global args
    if args.visualize or show_glyph:
        from visualization import (
            setup_screen, draw_all, draw_midlines, red, green, blue, draw_fat_point,
        )
    layer = glyph.foreground
    polylines = []
    polylines_to_draw = []
    alltriangles = []
    allmidpoints = []
    allmidlines = []
    dots = []
    # Calculate stroke width by first extracting vectors with no subdivision;
    # then convert to a Shapely polygon and calculate stroke width via the
    # 2*area / length algorithm. Then re-extract vectors with the real
    # stroke length.
    calculated_stroke_width = 0
    # Extract vectors with the real stroke width now
    approx_outlines = []
    for contour in layer:
        points = extrapolate_midpoints(list(contour))
        approx_vectors = extract_vectors(points)
        linestring = vectorpairs_to_linestring(approx_vectors)
        approx_outlines.append((linestring, contour))
    approx_parent_data = calculate_parents(approx_outlines)
    approx_level_data = levels(approx_parent_data)
    approx_level_data = calculate_immediate_children(approx_level_data)
    if show_glyph:
        screen = setup_screen()
        args.screen = screen
    else:
        screen = None
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
                m = averagepoint_as_tuple(line[0], line[1])
            holes = map(any_to_closedpolyline, [child['line'] for child in children])
            for hole in holes:
                for line in pairwise(hole):
                    m = averagepoint_as_tuple(line[0], line[1])
                polylines_to_draw.append(hole)
            outlines_to_filter = [outside_polyline] + holes
            real_trianglelines = list(filtertriangles(trianglelines, outlines_to_filter))
            midpoints = list(itermap_stopatvectors(averagepoint_as_tuplevector, real_trianglelines))
            midlines = list(calculate_midlines(midpoints))
            dots.extend(calculate_dots(midlines, args.radius, args.spacing))
            if show_glyph and args.show_dots:
                for dot in dots:
                    draw_fat_point(screen, dot, args.em, args.zoom, args.radius, color = blue)
            # Structure of midpoints now:
            # [t1, t2, t3] where t1, t2, t3 are: [m1, m2, m3] or [m1, m2] or [m1]
            # And m1, m2, m3 are (x, y)
            # Basically, each triangle's vectors have been changed to midpoints,
            # but the structure still remains
            for t in midpoints:
                if len(t) == 1:
                    for m in t:
                        pass
            allmidpoints.extend(midpoints)
            allmidlines.extend(map(vectorpairs_to_pointlist, midlines))
            #break  # Uncomment this to draw only the first "world"

    if show_glyph:
        draw_all(screen, polylines_to_draw, [], alltriangles, emsize = args.em, zoom = args.zoom,
            polylinecolor = (blue if args.show_glyph else None),
            trianglecolor = (red if args.show_triangles else None))
    if args.show_lines:
        draw_midlines(screen, allmidlines, allmidpoints, emsize = args.em, zoom = args.zoom, polylinecolor = green)
    return dots

def copy_glyph(orig_glyph, new_glyph):
    dots = extract_dots(orig_glyph, args.visualize)
    for dot in dots:
        contour = circle_at(dot, size=args.radius)
        contour.is_quadratic = new_glyph.foreground.is_quadratic
        new_glyph.foreground += contour
    for anchor in orig_glyph.anchorPoints:
        new_glyph.addAnchorPoint(*anchor)
    return new_glyph  # Probably not needed as the font now contains it

def make_triangles(polygon_data, holes = None):
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

DEBUG = True
def debug(s, *args, **kwargs):
    if not DEBUG:
        return
    if not args and not kwargs:
        print s
    else:
        print s.format(*args, **kwargs)

def parse_args():
    "Parse the arguments the user passed in"
    parser = argparse.ArgumentParser(description = textwrap.dedent("""
        This software creates a dotted font from any given input font. After creating
        the dotted font, you'll want to edit it by hand in FontForge to change the
        font name, copyright information, and so on.

        You'll want to use the -r and -s settings to adjust the radius and spacing
        of the given dots. Good values for radius are usually around 10-15, and good
        values for spacing are usually around 2.5 to 10.0 or so.

        Optionally, if you have PyGame installed (sudo apt-get install python-pygame)
        you can use the -t, -l, -d or -g options to watch the dotted font creation.

        Finally, if you give a glyph name (like "A") or Unicode codepoint (like U+0065)
        as a second parameter to this software, it will render only that glyph. This
        can be useful when tweaking your dot radius and spacing settings.
        """), epilog = textwrap.dedent("""
        Example of usage:
        python extractpoints.py /usr/share/fonts/truetype/padauk/Padauk.ttf -o trythis.ttf -r 12 -s 6.0
        """), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-v', '--verbose', action = "store_true", help = "Give more verbose error messages")
    parser.add_argument("inputfilename", nargs = "?", default = None, help = "Required: Font file (SFD or TTF format)")
    parser.add_argument("glyphname", nargs = "?", default = None, help = "Optional: Codepoint to render (in U+89AB form)")
    parser.add_argument('-o', '--output', action = "store", default = "output.ttf", help = "Filename of output dotted TTF")
    parser.add_argument('-z', '--zoom', action = "store", type = float, default = 1.0, help = "Zoom level of visualization (default 1.0)")
    parser.add_argument('-m', '--minstrokewidth', action = "store", type = float, default = 1, help = "Used for fine-tuning results (advanced usage only)")
    parser.add_argument('-M', '--maxstrokewidth', action = "store", type = float, default = 1e100, help = "Used for fine-tuning results (advanced usage only)")
    parser.add_argument('-t', '--show-triangles', action = "store_true", help = "Show the glyph triangulation")
    parser.add_argument('-l', '--show-lines', action = "store_true", help = "Show the midlines of the glyph")
    parser.add_argument('-d', '--show-dots', action = "store_true", help = "Show the dots that make the dotted version")
    parser.add_argument('-g', '--show-glyph', action = "store_true", help = "Show the glyph outline")
    parser.add_argument('-r', '--radius', action = "store", type = float, default = 12, help = "Radius of dots, in em units (default 12)")
    parser.add_argument('-s', '--spacing', action = "store", type = float, default = 6.0, help = "Spacing of dots, as a multiple of dot radius (default 6.0 for 600%%)")
    args = parser.parse_args()
    args.visualize = (args.show_triangles or args.show_lines or args.show_dots or args.show_glyph)
    if args.inputfilename is None:
        parser.print_help()
    return args

def main():
    """This is the main function we use that calls extraction_demo and also runs
    a sanity check to make sure everything works properly."""
    global args
    args = parse_args()
    if args.inputfilename is None:
        return 2
    if args.glyphname is None:
        create_dotted_font(args.inputfilename)
    else:
        extraction_demo(args.inputfilename, args.glyphname)
    return 0

if __name__ == "__main__":
    retcode = main()
    if retcode != 0:
        sys.exit(retcode)
