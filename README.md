fontinline
==========

Make inline stroke paths from an outline font

Requirements (Debian/Ubuntu):
    sudo apt-get install python-shapely python-pygame python-fontforge

Code structure
--------------

On a high level, the fontinline code operates by the following method:

1. Convert the glyph to a polygon made up of straight lines
   * Bezier curves will be converted to a series of straight lines by subdividing the Bezier curve N times, with N continually increasing until no two straight lines in the curve are at more than 3 degrees from each other. This produces a polygon that's a good approximation of the glyph, with a similar area and perimeter length.
1. Use that polygon to figure out the "stroke width" of the glyph:
   * First, assume the glyph has the general shape of a letter that can be drawn with a pen: it could be represented as one or more rectangles that have been bent into various curves or angles. (This assumption will fail for glyphs that are filled circles, like the period or colon, but will hold true for most letters in most writing systems.)
   * If that's the case, the "width" of those bent rectangles can be found by treating the glyph as a polygon, and using the formula 2 * (polygon's area) / (polygon's perimeter)
1. Convert the glyph to a polygon made up of straight lines AGAIN
   * This time, instead of converting Bezier curves to straight lines at no more than 3 degree angles to each other, the straight lines will have a minimum length of at least (glyph's stroke width). This is critical for the triangulation step that comes next: without this minimum length, the triangulation often ends up producing suboptimal results at curves. (TODO: Make a diagram of what happens when this step is omitted.)
1. Produce a Delauney triangulation of the glyph polygon
   * This uses the poly2tri Python library from http://github.com/hansent/python-poly2tri
1. Consider each separate triangle of the Delauney triangulation. Throw out the triangle sides that coincide with the side of a glyph. Take the centerpoint of each remaining side, and draw straight lines between each centerpoint. This produces a rough, but generally quite accurate, "midline" for the glyph.
1. Take the midline produced in the previous step and draw dots at a (tweakable) interval along each one.
