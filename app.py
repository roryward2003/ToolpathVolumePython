import os
import math
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from shapely.geometry import Polygon
from svgpathtools import svg2paths2, parse_path
from lxml import etree

app = Flask(__name__)
app.secret_key = 'banana'

UPLOAD_FOLDER = 'static/uploads'
SVG_FILENAME = 'uploaded.svg'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

stored_svg_path = os.path.join(UPLOAD_FOLDER, SVG_FILENAME)

def bezier_point(p0, p1, p2, p3, t):
    return (
        (1 - t) ** 3 * p0
        + 3 * (1 - t) ** 2 * t * p1
        + 3 * (1 - t) * t ** 2 * p2
        + t ** 3 * p3
    )

def parse_svg_shapes(filepath):
    tree = etree.parse(filepath)
    root = tree.getroot()
    shapes = []

    def add_polygon(poly):
        if poly.is_valid and poly.area > 0:
            shapes.append({'polygon': poly, 'nest_level': 0})

    for elem in root.iter():
        tag = etree.QName(elem).localname

        if tag == "rect":
            x = float(elem.attrib.get("x", 0))
            y = float(elem.attrib.get("y", 0))
            w = float(elem.attrib.get("width", 0))
            h = float(elem.attrib.get("height", 0))
            poly = Polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
            add_polygon(poly)

        elif tag == "circle":
            cx = float(elem.attrib.get("cx", 0))
            cy = float(elem.attrib.get("cy", 0))
            r = float(elem.attrib.get("r", 0))
            points = [
                (
                    cx + r * math.cos(2 * math.pi * i / 32),
                    cy + r * math.sin(2 * math.pi * i / 32),
                )
                for i in range(32)
            ]
            poly = Polygon(points)
            add_polygon(poly)

        elif tag == "path":
            d = elem.attrib.get("d")
            if not d:
                continue
            path = parse_path(d)

            for sub in path.continuous_subpaths():
                points = []
                for seg in sub:
                    p0 = seg.start
                    p3 = seg.end
                    if hasattr(seg, "control1") and hasattr(seg, "control2"):
                        # Cubic Bézier segment
                        p1 = seg.control1
                        p2 = seg.control2
                        for t in [i / 20 for i in range(101)]:
                            x = bezier_point(p0.real, p1.real, p2.real, p3.real, t)
                            y = bezier_point(p0.imag, p1.imag, p2.imag, p3.imag, t)
                            points.append((x, y))
                    elif seg.__class__.__name__ == "Arc":
                        # Arc segment — sample using the point() method
                        for t in [i / 100 for i in range(101)]:  # higher resolution for smoother arcs
                            pt = seg.point(t)
                            points.append((pt.real, pt.imag))
                    else:
                        # Line segment (or fallback)
                        points.append((p0.real, p0.imag))
                        points.append((p3.real, p3.imag))
                if len(points) >= 3:
                    poly = Polygon(points)
                    add_polygon(poly)

    return shapes

def compute_signed_area(shapes):
    for i, outer in enumerate(shapes):
        for j, inner in enumerate(shapes):
            if i != j and outer["polygon"].covers(inner["polygon"]):
                shapes[j]["nest_level"] += 1

    total_area = 0.0
    for shape in shapes:
        sign = 1 if shape["nest_level"] % 2 == 0 else -1
        total_area += sign * shape["polygon"].area
    return total_area

@app.route('/')
def home():
    return render_template('base.html')

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

@app.route('/calculate', methods=['POST'])
def calculate():
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

    if not os.path.exists(stored_svg_path):
        flash("No SVG uploaded.", 'error')
        return redirect(url_for('home'))

    try:
        shapes = parse_svg_shapes(stored_svg_path)
        area_mm2 = compute_signed_area(shapes)
        volume_ml = area_mm2 * depth / 1000
        flash(f"Calculated volume: {volume_ml:.2f} ml", 'success')
    except Exception as e:
        flash(f"Error calculating the area", 'error')

    return redirect(url_for('home'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
