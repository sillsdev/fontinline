"""Library for generally useful functions

Functions that are relatively self-contained, and which do math or iterator
operations (like averagepoint or pairwise) go in this library.
"""
import itertools
import functools
import fontforge
import math
import operator

def pairwise(source):
    """This funcion takes any iterable [a,b,c,d,...], and returns an iterator which yields (a,b), (b,c), (c,d)..."""
    source2 = itertools.islice(source, 1, None)
    for a, b in itertools.izip(source, source2):
        yield (a, b)

def by_threes(source):
    """This funcion takes any iterable [a,b,c,d,...], and returns an iterator which yields (a,b,c), (b,c,d), (c,d,e)..."""
    source2 = itertools.islice(source, 1, None)
    source3 = itertools.islice(source, 2, None)
    for a, b, c in itertools.izip(source, source2, source3):
        yield (a, b, c)

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

def ux(p):
    """Extract the x value of a point in any format"""
    try:
        result = p.x
    except AttributeError:
        result = p[0]
    return float(result)

def uy(p):
    """Extract the y value of a point in any format"""
    try:
        result = p.y
    except AttributeError:
        result = p[1]
    return float(result)

def angle(point1, point2):
    """Calculate the angle (in degrees) of the line between point1 and point2.
    Angles are calculated clockwise from the X axis, so that (0,0)->(1,0) is
    0 degrees, and (0,0)->(0,1) is 90 degrees."""
    ax = ux(point1)
    ay = uy(point1)
    bx = ux(point2)
    by = uy(point2)
    return 180.0 * math.atan2(by-ay, bx-ax) / math.pi

def similar_direction(point1, point2, point3, tolerance=30):
    """Check whether points 2 and 3 are in a similar direction from point 1.
    "Similar" can be redefined by changing the tolerance parameter (default 30 degrees)."""
    angle_to_p2 = angle(point1, point2)
    angle_to_p3 = angle(point1, point3)
    diff = abs(angle_to_p2 - angle_to_p3)
    while diff > 180:
        diff -= 360
    return abs(diff) < tolerance

def shallow_angle(a, b, c, tolerance=30):
    """Check whether the lines AB and BC form a shallow enough angle.
    Note that this is different from similar_direction, which checks AB and AC."""
    angle_ab = angle(a, b)
    angle_bc = angle(b, c)
    diff = abs(angle_ab - angle_bc)
    while diff > 180:
        diff -= 360
    #print "Angle", abs(diff), "and tolerance", tolerance, "=", (abs(diff) < tolerance)
    return abs(diff) < tolerance

def iterfilter_stopatvectors(predicate, nestedlist):
    """Special version of iterfilter that will stop at vectors.
    A "vector" here is defined as a list of two tuples."""
    def stop(item):
        return (isinstance(item, list) and len(item) == 2 and isinstance(item[0], tuple) and isinstance(item[1], tuple))
    for item in nestedlist:
        if stop(item):
            if predicate(item):
                yield item
        elif isinstance(item, list):
            yield list(iterfilter_stopatvectors(predicate, item))
        else:
            if predicate(item):
                yield item

def itermap_stopatvectors(f, nestedlist):
    """Special version of iterfilter that will stop at vectors.
    A "vector" here is defined as a list of two tuples."""
    def stop(item):
        return (isinstance(item, list) and len(item) == 2 and isinstance(item[0], tuple) and isinstance(item[1], tuple))
    for item in nestedlist:
        if stop(item):
            yield f(item)
        elif isinstance(item, list):
            yield list(itermap_stopatvectors(f, item))
        else:
            yield f(item)

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

def appended(elementlist, element):
    newlist = elementlist[:]
    newlist.append(element)
    return newlist

def k(anything):
    def f(blah):
        return anything
    return f

def iterfunc(func, startvalue):
    """This function takes a function and a start value and
    returns a function that will go through all elements of
    the list and the nested lists, and for each element such
    that the predicate is true, the function will modify the
    result using func and function(element)."""
    def identity(anything):
        return anything

    alwaysTrue = k(True)
    alwaysFalse = k(False)

    def newfunction(nestediterable, pred = alwaysTrue, function = identity, stop = alwaysFalse):
        result=startvalue
        for i in nestediterable:
            if stop(i):
                if pred(i):
                    result = func(result, function(i))
                continue
            try:
                iterable = iter(i)
            except TypeError:
                if pred(i):
                    print function(i)
                    result = func(result, function(i))
                    print result
            else:
                result = func(result, newfunction(iterable, pred, function))
        return result

    def new2(nestediterable, predicate, stop = alwaysFalse):
        return newfunction(nestediterable, pred = predicate, stop = stop)

    def new3(nestediterable, usedfunction, stop = alwaysFalse):
        return newfunction(nestediterable, function = usedfunction, stop = stop)
    return newfunction, new2, new3

iterany = iterfunc(operator.or_, True)
iterfiltermap, iterfilter, itermap = iterfunc(appended, [])

def compose(func1, func2):
    def newfunction(*args, **kwargs):
        return func1(func2(*args, **kwargs))
    return newfunction

comp = functools.partial(compose, operator.not_)

def are_lines_equal(v1, v2, epsilon=1e-9):
    simple_equality = all(are_points_equal(p1, p2, epsilon) for p1, p2 in zip(v1, v2))
    reversed_equality = all(are_points_equal(p1, p2, epsilon) for p1, p2 in zip(v1, reversed(v2)))
    #reversed_equality = False
    #simple_equality = False
    return (simple_equality or reversed_equality)

def averagepoint_as_ffpoint(point1, point2):
    """This function takes two fontforge points, and finds the average of them"""
    avgx = (point1.x + point2.x) / 2.0
    avgy = (point1.y + point2.y) / 2.0
    avgpoint = fontforge.point(avgx, avgy, True)
    return avgpoint

def averagepoint_as_tuple(point1, point2):
    """This function takes two tuples, and returns the average of them"""
    avgx = (point1[0] + point2[0]) / 2.0
    avgy = (point1[1] + point2[1]) / 2.0
    avgpoint = (avgx, avgy)
    return avgpoint

def averagepoint_as_tuplevector(v):
    """This function takes a vector of two tuples, and returns the midpoint of the vector."""
    return averagepoint_as_tuple(v[0], v[1])

def test(pred, a, b):
    if pred:
        return a
    else:
        return b

def closertest(point, point2, point3):
    return vectorlengthastuple(point1, point2)<vectorlengthastuple(point1, point3)

def closer(point1,point2,point3):
    return test(closertest(point1, point2, point3), point2, point3)

def closerish(point1,point2,point3,fudge):
    return test(vectorlengthastuple(point1, point2)<fudge*vectorlengthastuple(point1, point3), point2, point3)

def further(point1,point2,point3):
    return test(comp(closertest)(point1, point2, point3), point2, point3)

class AttrDict(dict):
    "A dict whose keys can be accessed as if they were attributes"
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self # See http://stackoverflow.com/a/14620633/2314532
