import io
import os
import unittest
from app import app, stored_svg_path

class SvgVolumeTestCase(unittest.TestCase):

    # Setup environment for testing
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Clean any environment changes
    def tearDown(self):
        if os.path.exists(stored_svg_path):
            os.remove(stored_svg_path)

    # Helper function for loading the test svg files
    def load_svg_file(self, filename):
        testdata_path = os.path.join("static", "testdata", filename)
        with open(testdata_path, 'rb') as f:
            return io.BytesIO(f.read())

    # Test that the home page appears
    def test_home(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SVG Volume Calculator", response.data)

    # Test that valid svg files upload
    def test_upload_valid_svg(self):
        svg_data = self.load_svg_file("Square-200x200.svg")
        data = {'svgfile': (svg_data, 'Square-200x200.svg')}
        response = self.client.post("/upload", data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SVG uploaded successfully!", response.data)

    # Test that invalid svg files do not upload
    def test_upload_invalid_file(self):
        data = {'svgfile': (b'not-an-svg', 'Invalid.txt')}
        response = self.client.post("/upload", data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid file format", response.data)

    # Calculation should not succeed without a valid svg files
    def test_calculate_without_upload(self):
        self.tearDown()
        response = self.client.post("/calculate", data={"title": "5"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No SVG uploaded", response.data)

    # Calculation should not succeed with an invalid depth
    def test_calculate_invalid_depth(self):
        svg_data = self.load_svg_file("Square-200x200.svg")
        self.client.post("/upload", data={'svgfile': (svg_data, 'Square-200x200.svg')}, content_type='multipart/form-data', follow_redirects=True)
        response = self.client.post("/calculate", data={"title": "oops"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid depth", response.data)

    # Calculation should not succeed with an empty depth
    def test_calculate_empty_depth(self):
        svg_data = self.load_svg_file("Square-200x200.svg")
        self.client.post("/upload", data={'svgfile': (svg_data, 'Square-200x200.svg')}, content_type='multipart/form-data', follow_redirects=True)
        response = self.client.post("/calculate", data={"title": ""}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid depth", response.data)
    
    # Simple cuboid calculation (200mm*200mm*10mm = 400ml)
    def test_calculate_valid_square(self):
        svg_data = self.load_svg_file("Square-200x200.svg")
        self.client.post("/upload", data={'svgfile': (svg_data, 'Square-200x200.svg')}, content_type='multipart/form-data', follow_redirects=True)
        response = self.client.post("/calculate", data={"title": "10"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Calculated volume: 400.00 ml", response.data)
    
    # Simple cuboid calculation with floating point depth (200mm*200mm*2.5mm = 100ml)
    def test_calculate_valid_square_float_depth(self):
        svg_data = self.load_svg_file("Square-200x200.svg")
        self.client.post("/upload", data={'svgfile': (svg_data, 'Square-200x200.svg')}, content_type='multipart/form-data', follow_redirects=True)
        response = self.client.post("/calculate", data={"title": "2.50"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Calculated volume: 100.00 ml", response.data)
    
    # Nested cuboids calculation ((200mm*200mm) - (100mm*100mm)) * 10mm = 300ml
    def test_calculate_valid_nested_squares(self):
        svg_data = self.load_svg_file("Squares-200x200-100x100.svg")
        self.client.post("/upload", data={'svgfile': (svg_data, 'Squares-200x200-100x100.svg')}, content_type='multipart/form-data', follow_redirects=True)
        response = self.client.post("/calculate", data={"title": "10"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Calculated volume: 300.00 ml", response.data)
    
    # Irregular shape with straight sides (complexArea * 10mm = 354.6ml)
    def test_calculate_valid_irregular_shape(self):
        svg_data = self.load_svg_file("IrregularShape.svg")
        self.client.post("/upload", data={'svgfile': (svg_data, 'IrregularShape.svg')}, content_type='multipart/form-data', follow_redirects=True)
        response = self.client.post("/calculate", data={"title": "10"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Calculated volume: 354.6", response.data)
    
    # Simple circlular prism calculation ((pi*100mm^2) * 10mm = 314.xxml)
    def test_calculate_valid_circle(self):
        svg_data = self.load_svg_file("ArcCircle-r100.svg")
        self.client.post("/upload", data={'svgfile': (svg_data, 'ArcCircle-r100.svg')}, content_type='multipart/form-data', follow_redirects=True)
        response = self.client.post("/calculate", data={"title": "10"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Calculated volume: 314", response.data)
    
    # Simple bezier circlular prism calculation ((pi*100mm^2) * 10mm = 314.xxml)
    def test_calculate_valid_bezier_circle(self):
        svg_data = self.load_svg_file("BezCircle-r100.svg")
        self.client.post("/upload", data={'svgfile': (svg_data, 'BezCircle-r100.svg')}, content_type='multipart/form-data', follow_redirects=True)
        response = self.client.post("/calculate", data={"title": "10"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Calculated volume: 314", response.data)
    
    # Nested circlular prisms calculation ((pi*100mm^2) - (pi*50mm^2)) * 10mm = 235.xxml)
    def test_calculate_valid_nested_circles_1(self):
        svg_data = self.load_svg_file("Circles-r100-r50.svg")
        self.client.post("/upload", data={'svgfile': (svg_data, 'Circles-r100-r50.svg')}, content_type='multipart/form-data', follow_redirects=True)
        response = self.client.post("/calculate", data={"title": "10"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Calculated volume: 235", response.data)
    
    # Nested circlular prisms calculation ((pi*100mm^2) - (pi*25mm^2) - (pi*25mm^2)) * 10mm = 274.xxml)
    def test_calculate_valid_nested_circles_2(self):
        svg_data = self.load_svg_file("NestedCircles-r100-r25-r25.svg")
        self.client.post("/upload", data={'svgfile': (svg_data, 'NestedCircles-r100-r25-r25.svg')}, content_type='multipart/form-data', follow_redirects=True)
        response = self.client.post("/calculate", data={"title": "10"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Calculated volume: 274", response.data)
        
    # Test bezier curve accuracy using (pi*100mm^2) = 314.13159....
    def test_calculate_bezier_accuracy_1(self):
        svg_data = self.load_svg_file("BezCircle-r100.svg")
        self.client.post("/upload", data={'svgfile': (svg_data, 'BezCircle-r100.svg')}, content_type='multipart/form-data', follow_redirects=True)
        response = self.client.post("/calculate", data={"title": "10"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Calculated volume: 314.1", response.data)
        
    # Test bezier curve accuracy using (pi*100mm^2) = 314.13159....
    def test_calculate_bezier_accuracy_2(self):
        svg_data = self.load_svg_file("BezCircle-r100.svg")
        self.client.post("/upload", data={'svgfile': (svg_data, 'BezCircle-r100.svg')}, content_type='multipart/form-data', follow_redirects=True)
        response = self.client.post("/calculate", data={"title": "10"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(
                val in response.data
                for val in [b"314.13", b"314.14", b"314.15", b"314.16"]
            ),
            "Calculated volume not in expected range"
        )

if __name__ == "__main__":
    unittest.main()
