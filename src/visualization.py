"""Library for visualizing our results"""

import pygame
import itertools
import decimal
import time
from pygame.locals import QUIT, KEYDOWN, MOUSEBUTTONDOWN
from pygame.gfxdraw import trigon, line, pixel, filled_circle
from generalfuncs import pairwise

red = pygame.Color(255, 0, 0)
green = pygame.Color(0, 255, 0)
blue = pygame.Color(0, 0, 255)

def setup_screen():
    SCREEN_SIZE = (1280,800)
    pygame.init()
    screen = pygame.display.set_mode(SCREEN_SIZE,0,8)
    pygame.display.set_caption('Triangulation of glyph (name goes here)')
    return screen

def wait_for_keypress(emsize=1024, zoom=1.0):
    done = False
    while not done:
        e = pygame.event.wait()
        if (e.type == QUIT):
            done = True
            break
        elif (e.type == KEYDOWN):
            done = True
            break
        elif (e.type == MOUSEBUTTONDOWN):
            x, y = e.pos
            # Reconstruct glyph coords from screen coords
            x = float(x) / zoom
            y = emsize-(float(y) / zoom)
            print (x, y)
            import sys
            sys.stdout.flush()
            continue

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

def draw_fat_point(screen, point, emsize=1024, zoom=1.0, color=red):
    deczoom = decimal.Decimal(zoom)
    try:
        x = int(point.x * zoom)
        y = int((emsize-point.y) * zoom)
    except AttributeError:
        x = int(point[0] * zoom)
        y = int((emsize-point[1]) * zoom)
    except TypeError:
        try:
            x = int(point.x * deczoom)
            y = int((emsize-point.y) * deczoom)
        except AttributeError:
            x = int(point[0] * deczoom)
            y = int((emsize-point[1]) * deczoom)
    filled_circle(screen, x, y, 10, color)

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

def draw_midlines(screen, polylines, midpoints, emsize=1024, zoom=1.0, polylinecolor=green, midpointcolor=red):
    """This function takes the list of polylines and midpoints, and draws them in pygame."""
    global args
    deczoom = decimal.Decimal(zoom)
    for m in midpoints:
        x = int(m[0] * deczoom)
        y = int((emsize-m[1]) * deczoom)
        #print (x,y)
        pixel(screen, x, y, midpointcolor)

    # Close the polylines loop again prior to drawing
    for polyline in polylines:
        #polyline.append(polyline[0])
        flipped = flip_polyline(polyline, emsize)
        for a, b in pairwise(flipped):
            x1 = int(a[0] * deczoom)
            y1 = int(a[1] * deczoom)
            x2 = int(b[0] * deczoom)
            y2 = int(b[1] * deczoom)
            line(screen, x1, y1, x2, y2, polylinecolor)
            pygame.display.update()
    # Show result

