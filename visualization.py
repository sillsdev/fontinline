from __future__ import division, print_function

"""Library for visualizing our results"""

import pygame
import itertools
import time
from pygame.locals import QUIT, KEYDOWN, MOUSEBUTTONDOWN
from pygame.gfxdraw import trigon, line, pixel, filled_circle
from generalfuncs import pairwise, ux, uy
from dataconvert import get_triangle_point

red = pygame.Color(255, 0, 0)
green = pygame.Color(0, 255, 0)
blue = pygame.Color(0, 128, 255)

def setup_screen():
    SCREEN_SIZE = (1280, 800)
    pygame.init()
    screen = pygame.display.set_mode(SCREEN_SIZE, 0, 8)
    pygame.display.set_caption('Triangulation of glyph (name goes here)')
    return screen

def wait_for_keypress(emsize = 1024, zoom = 1.0):
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
            print((x, y))
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
                result.append(point.__class__(x, y))
            except AttributeError:
                x, y = point[0], emsize-point[1]
                result.append(tuple([x, y]))
    return result

def draw_fat_point(screen, point, emsize = 1024, zoom = 1.0, radius = 4, color = red):
    x = int(ux(point) * zoom)
    y = int((emsize-uy(point)) * zoom)
    # Radius given in em units; convert to screen units
    screen_height = screen.get_size()[1]
    pixel_radius = radius * screen_height / float(emsize)
    filled_circle(screen, x, y, int(pixel_radius), color)

def draw_all(screen, polylines, holes, triangles, emsize = 1024, zoom = 1.0, polylinecolor = green, holecolor = blue, trianglecolor = red):
    """This function takes the list of polylines and holes and the triangulation, and draws it in pygame.
    This function is pending deprecation."""
    global args

    if trianglecolor is not None:
        for t in triangles:
            a = get_triangle_point(t, 0)
            b = get_triangle_point(t, 1)
            c = get_triangle_point(t, 2)
            x1 = int(ux(a) * zoom)
            y1 = int((emsize-uy(a)) * zoom)
            x2 = int(ux(b) * zoom)
            y2 = int((emsize-uy(b)) * zoom)
            x3 = int(ux(c) * zoom)
            y3 = int((emsize-uy(c)) * zoom)
            trigon(screen, x1, y1, x2, y2, x3, y3, trianglecolor)

    # Close the polylines loop again prior to drawing
    if polylinecolor is not None:
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
    if holecolor is not None:
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

def draw_midlines(screen, polylines, midpoints, emsize = 1024, zoom = 1.0, polylinecolor = green, midpointcolor = red):
    """This function takes the list of polylines and midpoints, and draws them in pygame."""
    global args
    #for m in midpoints:
        #x = int(m[0] * zoom)
        #y = int((emsize-m[1]) * zoom)
        #print((x, y))
        #pixel(screen, x, y, midpointcolor)

    # Close the polylines loop again prior to drawing
    for polyline in polylines:
        #polyline.append(polyline[0])
        flipped = flip_polyline(polyline, emsize)
        for a, b in pairwise(flipped):
            x1 = int(a[0] * zoom)
            y1 = int(a[1] * zoom)
            x2 = int(b[0] * zoom)
            y2 = int(b[1] * zoom)
            line(screen, x1, y1, x2, y2, polylinecolor)
            pygame.display.update()
    # Show result

if __name__ == '__main__':
    sys.stderr.write('Please run extractpoints.py, not this file.\n')
