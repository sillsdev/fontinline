"""Library for visualizing our results"""

import pygame
import itertools
import decimal
import time
from pygame.locals import QUIT, KEYDOWN
from pygame.gfxdraw import trigon, line, pixel

red = pygame.Color(255, 0, 0)
green = pygame.Color(0, 255, 0)
blue = pygame.Color(0, 0, 255)

def is_within(line, polygon):
    # This is not where this function should live long-term...
    from dataconvert import any_to_linestring, any_to_polygon
    line = any_to_linestring(line)
    polygon = any_to_polygon(polygon, [])
    return line.difference(polygon).is_empty

def pairwise(source):
    # TODO: Import this function from generalfuncs.py instead of duplicating it
    """This funcion takes any iterable [a,b,c,d,...], and returns an iterator which yields (a,b), (b,c), (c,d)..."""
    source2 = itertools.islice(source, 1, None)
    for a, b in itertools.izip(source, source2):
        yield (a, b)

def setup_screen():
    SCREEN_SIZE = (1280,800)
    pygame.init()
    screen = pygame.display.set_mode(SCREEN_SIZE,0,8)
    pygame.display.set_caption('Triangulation of glyph (name goes here)')
    return screen

def wait_for_keypress():
    done = False
    while not done:
        e = pygame.event.wait()
        if (e.type == QUIT):
            done = True
            break
        elif (e.type == KEYDOWN):
            done = True
            break

def flip_polyline(polylinelist, emsize):
    """This function takes a list of lists of tuples (the list of polylines), and inverts the y coordinate of each point
    because the coordinate systems for fontforge are different than the coordinate systems for the p2t program."""
    # Used for visualization only
    result = []
    for point in polylinelist:
        #for point in polyline:
            try:
                x, y = point.x, emsize-point.y
                result.append(point.__class__(x,y))
            except AttributeError:
                x, y = point[0], emsize-point[1]
                result.append(tuple([x,y]))
    return result

def draw_all(screen, polylines, holes, triangles, emsize=1024, zoom=1.0, polylinecolor=green, holecolor=blue, trianglecolor=red):
    """This function takes the list of polylines and holes and the triangulation, and draws it in pygame.
    This function is pending deprecation."""
    global args

    for t in triangles:
        x1 = int(t.a.x * zoom)
        y1 = int((emsize-t.a.y) * zoom)
        x2 = int(t.b.x * zoom)
        y2 = int((emsize-t.b.y) * zoom)
        x3 = int(t.c.x * zoom)
        y3 = int((emsize-t.c.y) * zoom)
        trigon(screen, x1, y1, x2, y2, x3, y3, trianglecolor)

    # Close the polylines loop again prior to drawing
    for polyline in polylines:
        if hasattr(polyline, 'coords'):
            polyline = list(polyline.coords)
        polyline.append(polyline[0])
        flipped = flip_polyline(polyline, emsize)
        for a, b in pairwise(flipped):
            x1 = int(a[0] * zoom)
            y1 = int(a[1] * zoom)
            x2 = int(b[0] * zoom)
            y2 = int(b[1] * zoom)
            line(screen, x1, y1, x2, y2, polylinecolor)

    # Same for holes
    for hole in holes:
        if hasattr(hole, 'coords'):
            hole = list(hole.coords)
        hole.append(hole[0])
        flipped = flip_polyline(hole, emsize)
        for a, b in pairwise(flipped):
            x1 = int(a[0] * zoom)
            y1 = int(a[1] * zoom)
            x2 = int(b[0] * zoom)
            y2 = int(b[1] * zoom)
            line(screen, x1, y1, x2, y2, holecolor)

    # Show result
    pygame.display.update()

def draw_midlines(screen, midlines, polylines, midpoints, emsize=1024, zoom=1.0, polylinecolor=green, midpointcolor=red):
    """This function takes the list of polylines and midpoints, and draws them in pygame.

    Parameters:
        screen = the Pygame screen object to draw on
        midlines = the calculated midlines of the object
        polylines = the polygon contours we should never go outside
        """
    global args
    deczoom = decimal.Decimal(zoom)
    for m in midpoints:
        x = int(m[0] * deczoom)
        y = int((emsize-m[1]) * deczoom)
        #print (x,y)
        pixel(screen, x, y, midpointcolor)

    for midline in midlines:
        flipped = flip_polyline(midline, emsize)
        for a, b in pairwise(flipped):
            skip_this = True
            for polyline in polylines:
                if is_within([a,b], flip_polyline(polyline.coords, emsize)):
                    skip_this = False
            if skip_this:
                continue
            x1 = int(a[0] * deczoom)
            y1 = int(a[1] * deczoom)
            x2 = int(b[0] * deczoom)
            y2 = int(b[1] * deczoom)
            line(screen, x1, y1, x2, y2, polylinecolor)
            pygame.display.update()
    # Show result

