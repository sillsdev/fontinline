#!/usr/bin/env python

import fontforge
import time
import optparse
import argparse
import sys
import os, os.path
import itertools
import shapely
import warnings
import decimal
import math
from shapely.geometry import Polygon, LineString, Point
sys.path.append('../../python-poly2tri')
import p2t
sys.path.remove('../../python-poly2tri')

from dataconvert import (
    any_to_linestring, any_to_polygon, ff_to_tuple, closedpolyline2vectorset,
    convert_polyline_to_polytri_version, triangles2vectorset,
    vectorpairs_to_pointlist, triangle2vectors, p2dt)
from visualization import (setup_screen, draw_all, draw_midlines,
                           wait_for_keypress, red, green, blue)

DEFAULT_FONT='/usr/share/fonts/truetype/padauk/Padauk.ttf'
DEFAULT_GLYPH='u1021'

#==============
#This section is for functions that calculate and return a different data type
#==============

def are_points_equal(a, b, epsilon=1e-9):
    """Compares points a and b and returns true if they're equal.

    "Equal", here, is defined as "the difference is less than epsilon" since
    we're dealing with floats.

    Points a and b can be either Fontforge point objects, or tuples."""
    try:
        x1, y1 = a.x, a.y
        x2, y2 = b.x, b.y
    except AttributeError:
        x1, y1 = a[0], a[1]
        x2, y2 = b[0], b[1]
    return (abs(x1-x2) < epsilon) and (abs(y1-y2) < epsilon)

def calculate_parents(polylines):
    """This function takes a list of fontforge points and turns it into a list of dictionaries.
    Each dictionary has the polygon, the list of points, the children (the polygons inside the
    given polygon, and the parents (the polygons containing the given polygon)"""
    if polylines==[]:
        return []
    polygons=[]
    for i in polylines:
        d=dict()
        d['poly']=Polygon(ff_to_tuple(i))
        d['line']=i
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

def vectorlengthastuple(point1, point2):
    """This function takes two tuple-style points, and returns the distance between them"""
    xdiff=float(point1[0]-point2[0])
    ydiff=float(point1[1]-point2[1])
    squaredlength=xdiff**2+ydiff**2
    length=squaredlength**0.5
    return length

def vectorlength(point1, point2):
    """This function takes two fontforge points, and returns the distance between them"""
    xdiff=point1.x-point2.x
    ydiff=point1.y-point2.y
    squaredlength=xdiff**2+ydiff**2
    length=squaredlength**0.5
    return length

def averagepoint(point1, point2):
    """This function takes two fontforge points, and finds the average of them"""
    avgx = (point1.x + point2.x) / 2.0
    avgy = (point1.y + point2.y) / 2.0
    avgpoint = fontforge.point(avgx, avgy, True)
    return avgpoint

def averagepoint_astuple(point1, point2):
    """This function takes two tuples, and returns the average of them"""
    avgx = (point1[0] + point2[0]) / decimal.Decimal(2)
    avgy = (point1[1] + point2[1]) / decimal.Decimal(2)
    avgpoint = (avgx, avgy)
    return avgpoint

def pairwise(source):
    """This funcion takes any iterable [a,b,c,d,...], and returns an iterator which yields (a,b), (b,c), (c,d)..."""
    source2 = itertools.islice(source, 1, None)
    for a, b in itertools.izip(source, source2):
        yield (a, b)

def extrapolate_midpoints(points):
    """This function takes a list of fontforge points and if two consecutive points are off-curve
    it extrapolates the on-curve point between them."""
    if not (points[-1] == points[0]):
        points.append(points[0])  # Close the curve
    result = []
    for a, b in pairwise(points):
        if a.on_curve or b.on_curve:
            # No need to extrapoalate for this pair
            result.append(a)
        else:
            midpoint = averagepoint(a, b)
            result.append(a)
            result.append(midpoint)
    # Last point will not have been part of any pairs, so it won't have been
    # appended. Append it now.
    result.append(points[-1])
    return result

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
    """This function takes three points (tuples), and yields n-1 evenly spaced
    points (tuples) along the bezier defined by those points"""
    if n<=0:
        raise ValueError("you cannot subdivide into less than one piece")
    if not type(n)==int:
        raise ValueError("you cannot subdivide into a non-integer number of pieces")
    i=0
    while i<=n:
        result1 = ((n-i)**2)*points[0].x+2*i*(n-i)*points[1].x+i*i*points[2].x
        result2 = ((n-i)**2)*points[0].y+2*i*(n-i)*points[1].y+i*i*points[2].y
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

def closer(point1,point2,point3):
    if vectorlengthastuple(point1,point2)<vectorlengthastuple(point1,point3):
        return point2
    else:
        return point3

def closerish(point1,point2,point3,fudge):
    if vectorlengthastuple(point1,point2)<fudge*vectorlengthastuple(point1,point3):
        return point2
    else:
        return point3

def further(point1,point2,point3):
    if vectorlengthastuple(point1,point2)>vectorlengthastuple(point1,point3):
        return point2
    else:
        return point3

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

def pointscloserthan(point,points,radius):
    closelist=[]
    for i in points:
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

#================
#This section is for functions that actually do things beyond calculations and converting between data types
#================

def extractvectors(points,length):
    """Note: points argument should be a list (or generator) of FF points."""
    points = list(points)
    for candidate in extractbeziers(points):
        lineorbezierlength=float(vectorlength(candidate[-1],candidate[0]))
        subdivision=int(math.ceil(lineorbezierlength/length))
        if len(candidate) == 2:
            # It's a vector
            subdivided=list(subdivideline(candidate,subdivision))
            for v in pairwise(subdivided):
                yield v
        else:
            #change this to variable later
            subdivided=list(subdividebezier(candidate,subdivision))
            for v in pairwise(subdivided):
                yield v

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
    # Result was 1: so there is exactly one contour. If there were more, we'd
    # loop through them each in turn.
    polylines = []
    polylines_set = set()
    triangles = []
    #holes = []
    for contour in layer:
        # At this point, we're dealing with FontForge objects (lists of FF points, and so on)
        points = list(contour)
        pointlist_with_midpoints = extrapolate_midpoints(points)
        vectors = extractvectors(pointlist_with_midpoints,args.minstrokelength)
        #polyline = ff_to_tuple(vectorpairs_to_pointlist(vectors))
        polyline = vectorpairs_to_pointlist(vectors)
        polylines.append(any_to_linestring(polyline))
        polylines_set = polylines_set.union(closedpolyline2vectorset(polyline))
    parent_data = calculate_parents(polylines)
    level_data = levels(parent_data)
    level_data = calculateimmediatechildren(level_data)
    booleanvalue=True
    for level in level_data[::2]:
        for poly in level:
            triangles.extend(make_triangles(poly, poly.get('immediatechildren', [])))
#             if booleanvalue:
            immediatechildrenlines=[]
            for i in poly.get('immediatechildren', []):
                immediatechildrenlines.append(i['line'])
            polygon=any_to_polygon(poly['line'],immediatechildrenlines)
            booleanvalue=False
            area=polygon.area
            length=polygon.length
            width=2*area/length
            print width

        #if contour.isClockwise():
            #polylines.append(polyline)
        #else:
            #holes.append(polyline)
    triangles_set = triangles2vectorset(triangles)
    midpoints_set = triangles_set - polylines_set
    midpoints = [averagepoint_astuple(v[0], v[1]) for v in midpoints_set]
    screen = setup_screen()
    draw_all(screen, polylines, [], triangles, emsize=args.em, zoom=args.zoom, polylinecolor=blue, trianglecolor=red)
    #draw_midlines(screen,[],midpoints)
    #lines=points_to_all_lines(midpoints, width*1.2)
    #draw_midlines(screen, lines, midpoints, polylinecolor=green)
    closesorted=closesort(midpoints,width)
    closesorted.append(closesorted[0])
    draw_midlines(screen, [closesorted], midpoints, emsize=args.em, zoom=args.zoom, polylinecolor=green)
    wait_for_keypress()
    return points
    # Note that there may be several off-curve points in a sequence, as with
    # the U+1015 example I chose here. The FontForge Python documentation at
    # one point talks about "the TrueType idiom where an on-curve point mid-way
    # between its control points may be omitted, leading to a run of off-curve
    # points (with implied but unspecified on-curve points between them)."

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

# Demo of how to extract the control points from a font.
# Run "sudo apt-get install fonts-sil-padauk" before calling this function.
# Extending this function to arbitrary fonts and glyphs is left as an exercise
# for the reader. ;-)

def parse_args():
    "Parse the arguments the user passed in"
    parser = argparse.ArgumentParser(description="Demonstrate parsing arguments")
    #parser.add_argument('--help', help="Print the help string")
    parser.add_argument('-v', '--verbose', action="store_true", help="Give more verbose error messages")
    parser.add_argument("inputfilename", nargs="?", default=DEFAULT_FONT, help="Font file (SFD or TTF format)")
    parser.add_argument("glyphname", nargs="?", default=DEFAULT_GLYPH, help="Glyph name to extract")
    parser.add_argument('-z', '--zoom', action="store", type=float, default=1.0, help="Zoom level (default 1.0)")
    parser.add_argument('-m', '--minstrokelength', action="store", type=float, default=-1, help="The minimum stroke length")
    args = parser.parse_args()
    args.svgfilename = args.glyphname + '.svg'
    args.datfilename = args.glyphname + '.dat'
    return args

def main():
    """This is the main function we use that calls extraction_demo and also runs
    a sanity check to make sure everything works properly."""
    global args
    args = parse_args()
    extraction_demo(args.inputfilename, args.glyphname)
    #extraction_demo('/usr/share/fonts/truetype/padauk/Padauk.ttf',0xaa75)
    #extraction_demo('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',0x0e3f)
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
