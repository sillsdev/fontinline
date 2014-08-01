fontinline
==========

Make inline stroke paths from an outline font

Requirements (Debian/Ubuntu):
    sudo apt-get install git python-shapely python-fontforge cython build-essential python-dev
    sudo apt-get install python-pygame  # Optional
    git clone http://github.com/hansent/python-poly2tri
    git clone http://github.com/sillsdev/fontinline
    cd python-poly2tri
    python setup.py build_ext -i
    ls p2t.so || echo Something failed, fix it and rebuild p2t
    cp p2t.so ../fontinline
    cd ../fontinline
    python extractpoints.py inputfont.ttf -o outputfont.ttf

Note that python-pygame is optional: if you never use the "--show-foo" options
(where foo can be triangles, lines, dots or glyph) or their one-letter short
versions (-t, -l, -d or -g), then the pygame dependency will not be required.
If you try to use those options and pygame is not installed, you'll see
"ImportError: No module named pygame". If that happens, simply run the
"sudo apt-get install python-pygame" command and try again.

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

TODO
----

* Place dots at 0.0 and 1.0 of endpoints (sometimes they're not landing
  at the end of the midlines, which seems like a bug)
* If endpoint dots within 50% of another dot, drop other dot
    * (This calculation might be slightly tricky, but will be
      simplified if we keep track of endpoint dots specially)
* Future ideas for possible improvement:
    * Before dotting, run a smoothing algorithm on all segments (lines, curves)
      so that, for example, the letter B in Padauk font will have its lower
      curve look a bit smoother. (Difficulty: hard)
    * At intersection points, look at the curve direction (2nd derivative)
      of the lines leading into the intersection. Extend them with the same
      2nd derivative and look at where those extended lines would naturally
      intersect. (Difficulty: unknown)
    * Looking at the letter H as it stands with current code, another smoothing
      (or kink-removing) algorithm, applied to the vertical segments, might
      straighten them out. This would require turning the 5 segments that
      current code produces for H into 3 segments, by detecting the angle of
      the joins and saying "Angle is less than X degrees, join these segments"
      for smallish values of X (measured against the smoothly-extended lines).
      (Difficulty: medium)
    * After drawing intersections, we could also extend the endpoints of the
      midlines (e.g., the starting and ending points in the letter C) and take
      them, with the same "keep the second derivative similar" algorithm, all
      the way until they intersect with one side of the tesselation triangle.
