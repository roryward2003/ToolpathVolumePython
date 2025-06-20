import math
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from shapely.geometry import Polygon
from svgpathtools import svg2paths2, parse_path
from lxml import etree

# Setup
app = Flask(__name__)
app.secret_key = 'banana'
UPLOAD_FOLDER = 'static/uploads'
SVG_FILENAME = 'uploaded.svg'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
stored_svg_path = os.path.join(UPLOAD_FOLDER, SVG_FILENAME)
CIRCLE_SAMPLES = 1000
ELLIPSE_SAMPLES = 1000
CURVE_SAMPLES = 1000

# Bezier parse function using t as the scale
def bezier_point(p0, p1, p2, p3, t):
    return (
        (1 - t) ** 3 * p0
        + 3 * (1 - t) ** 2 * t * p1
        + 3 * (1 - t) * t ** 2 * p2
        + t ** 3 * p3
    )

# Parse svg from filepath into a list of nested polygons
def parse_svg_shapes(filepath):
    tree = etree.parse(filepath)
    root = tree.getroot()
    shapes = []

    # Add a polygon to the list with initial nesting level 0
    def add_polygon(poly):
        if poly.is_valid and poly.area > 0:
            shapes.append({'polygon': poly, 'nest_level': 0})

    # Iterate over the svg elements using lxml to parse the XML document
    for elem in root.iter():
        tag = etree.QName(elem).localname

        # Rectangles
        if tag == "rect":
            x = float(elem.attrib.get("x", 0))
            y = float(elem.attrib.get("y", 0))
            w = float(elem.attrib.get("width", 0))
            h = float(elem.attrib.get("height", 0))
            
            # Convert from points to a polygon
            poly = Polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
            add_polygon(poly)

        # Circles
        elif tag == "circle":
            cx = float(elem.attrib.get("cx", 0))
            cy = float(elem.attrib.get("cy", 0))
            r = float(elem.attrib.get("r", 0))
            points = [
                (
                    cx + r * math.cos(2 * math.pi * i / CIRCLE_SAMPLES),
                    cy + r * math.sin(2 * math.pi * i / CIRCLE_SAMPLES),
                )
                for i in range(CIRCLE_SAMPLES+1)
            ]

            # Convert from points to a polygon
            poly = Polygon(points)
            add_polygon(poly)

        # Ellipses
        elif tag == "ellipse":
            cx = float(elem.attrib.get('cx', 0))
            cy = float(elem.attrib.get('cy', 0))
            rx = float(elem.attrib.get('rx', 0))
            ry = float(elem.attrib.get('ry', 0))
            points = [
                (
                    cx + rx * math.cos(2 * math.pi * i / ELLIPSE_SAMPLES),
                    cy + ry * math.cos(2 * math.pi * i / ELLIPSE_SAMPLES),
                )
                for i in range(ELLIPSE_SAMPLES+1)
            ]
            
            # Convert from points to a polygon
            poly = Polygon(points)
            add_polygon(poly)

        # Any other path
        elif tag == "path":

            # Extract the path from the XML tree
            data = elem.attrib.get("d")
            if not data:
                continue
            path = parse_path(data)

            # For each subpath, approximate with straight lines and plot all points
            for sub in path.continuous_subpaths():
                points = []
                for seg in sub:
                    p0 = seg.start
                    p3 = seg.end
                    
                    # Cubic Bézier segment has two control handles
                    if hasattr(seg, "control1") and hasattr(seg, "control2"):
                        p1 = seg.control1
                        p2 = seg.control2

                        # Sample using custom helper method
                        for t in [i / CURVE_SAMPLES for i in range(CURVE_SAMPLES+1)]:
                            x = bezier_point(p0.real, p1.real, p2.real, p3.real, t)
                            y = bezier_point(p0.imag, p1.imag, p2.imag, p3.imag, t)
                            points.append((x, y))

                    # Arc segment has just one control handle
                    elif seg.__class__.__name__ == "Arc":

                        # Sample using the point() method
                        for t in [i / CURVE_SAMPLES for i in range(CURVE_SAMPLES+1)]:
                            pt = seg.point(t)
                            points.append((pt.real, pt.imag))

                    else:
                        # Line segment (or fallback)
                        points.append((p0.real, p0.imag))
                        points.append((p3.real, p3.imag))

                # Convert from points to a polygon iff its a valid shape
                if len(points) >= 3:
                    poly = Polygon(points)
                    add_polygon(poly)

    return shapes

# Calculate the sign for addition based on level of nesting inside other shapes
# Overlaps don't need consideration because they would not from a valid CNC toolpath
def compute_signed_area(shapes):
    for i, outer in enumerate(shapes):
        for j, inner in enumerate(shapes):
            if i != j and outer["polygon"].covers(inner["polygon"]):
                shapes[j]["nest_level"] += 1

    # Calculate the signed area to ensure only removed material is considered
    total_area = 0.0
    for shape in shapes:
        sign = 1 if shape["nest_level"] % 2 == 0 else -1
        total_area += sign * shape["polygon"].area
    return total_area

# Home endpoint
@app.route('/')
def home():
    return render_template('base.html')

# Upload SVG file endpoint
@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('svgfile')
    if file and file.filename.endswith('.svg'):
        filename = secure_filename(SVG_FILENAME)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        flash('SVG uploaded successfully!', 'success')
    else:
        flash('Invalid file format. Please upload an SVG file.', 'error')
    return redirect(url_for('home'))

# Caculate volume using both the user inputted depth and uploaded SVG file
@app.route('/calculate', methods=['POST'])
def calculate():

    # Ensure depth is a valid numerical value
    depth_input = request.form.get('title')
    try:
        if not depth_input:
            raise ValueError("No depth entered.")
        if depth_input.startswith('.'):
            depth_input = '0' + depth_input
        if not all(c.isdigit() or c == '.' for c in depth_input) or depth_input.count('.') > 1:
            raise ValueError("Invalid depth")
        depth = float(depth_input)
    except Exception as e:
        flash(f"Invalid depth", 'error')
        return redirect(url_for('home'))

    # Ensure the svg file exists
    if not os.path.exists(stored_svg_path):
        flash("No SVG uploaded.", 'error')
        return redirect(url_for('home'))

    # Calculate the volume
    try:
        shapes = parse_svg_shapes(stored_svg_path)
        area_mm2 = compute_signed_area(shapes)
        volume_ml = area_mm2 * depth / 1000
        flash(f"Calculated volume: {volume_ml:.2f} ml", 'success')
    except Exception as e:
        flash(f"Error calculating the area", 'error')

    # Return the updated homepage with results and/or error messages updated
    return redirect(url_for('home'))

# App entry point
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
