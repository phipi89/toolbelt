# Run: uv run --with pikepdf --with pillow --with 'pymupdf<2' python -m unittest discover -s misc -p test_shrink_pdf.py
import importlib.util
import random
import tempfile
import unittest
from pathlib import Path

import pikepdf
import pymupdf
from PIL import Image, ImageChops, ImageCms, ImageStat

spec = importlib.util.spec_from_file_location(
    "shrink_pdf", Path(__file__).with_name("shrink_pdf.py")
)
shrink_pdf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shrink_pdf)


class CompressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "input.pdf"
        self.output = Path(self.temp.name) / "output.pdf"

    def fixture(self, placements=(300,), shared_mask=False, line_art=False):
        rng = random.Random(123)
        image = Image.frombytes("RGB", (900, 600), rng.randbytes(900 * 600 * 3))
        if line_art:
            image = image.point(lambda value: 255 if value > 127 else 0)
        pdf = pikepdf.Pdf.new()
        profile = pdf.make_stream(
            ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        )
        profile.N = 3
        obj = pdf.make_stream(image.tobytes())
        obj.Type = pikepdf.Name.XObject
        obj.Subtype = pikepdf.Name.Image
        obj.Width, obj.Height = image.size
        obj.BitsPerComponent = 8
        obj.ColorSpace = pikepdf.Array([pikepdf.Name.ICCBased, profile])
        alpha = Image.linear_gradient("L").resize(image.size)
        mask = pdf.make_stream(alpha.tobytes())
        mask.Type, mask.Subtype = pikepdf.Name.XObject, pikepdf.Name.Image
        mask.Width, mask.Height = image.size
        mask.BitsPerComponent, mask.ColorSpace = 8, pikepdf.Name.DeviceGray
        obj.SMask = mask
        for width in placements:
            page = pdf.add_blank_page(page_size=(1000, 700))
            page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im=obj))
            page.Contents = pdf.make_stream(
                f"q 0.2 0.5 0.7 rg 0 0 1000 700 re f Q q {width} 0 0 {width * 2 / 3} 20 20 cm /Im Do Q".encode()
            )
        if shared_mask:
            other = pdf.make_stream(image.tobytes())
            for key in (
                "/Type",
                "/Subtype",
                "/Width",
                "/Height",
                "/BitsPerComponent",
                "/ColorSpace",
                "/SMask",
            ):
                other[key] = obj[key]
            page.Resources.XObject.Other = other
            page.Contents.write(
                page.Contents.read_bytes() + b" q 150 0 0 100 600 400 cm /Other Do Q"
            )
        pdf.save(self.source)

    def test_transparency_profile_and_content_survive_downsampling(self):
        self.fixture()
        shrink_pdf.compress(self.source, self.output)
        with pikepdf.open(self.source) as original, pikepdf.open(self.output) as result:
            before = original.pages[0].Resources.XObject.Im
            after = result.pages[0].Resources.XObject.Im
            self.assertEqual((after.Width, after.Height), (600, 400))
            self.assertEqual((after.SMask.Width, after.SMask.Height), (600, 400))
            self.assertNotEqual(after.SMask.get("/Filter"), "/DCTDecode")
            self.assertEqual(
                before.ColorSpace[1].read_bytes(), after.ColorSpace[1].read_bytes()
            )
            self.assertEqual(
                original.pages[0].Contents.read_bytes(),
                result.pages[0].Contents.read_bytes(),
            )
            self.assertEqual(result.check_pdf_syntax(), [])
        # Compare composited output on a coloured background, including alpha edges.
        with pymupdf.open(self.source) as a, pymupdf.open(self.output) as b:
            images = [
                Image.frombytes("RGB", (1000, 700), d[0].get_pixmap().samples)
                for d in (a, b)
            ]
            difference = ImageStat.Stat(ImageChops.difference(*images))
            self.assertLess(max(difference.mean), 5)
        self.assertLess(self.output.stat().st_size, self.source.stat().st_size)

    def test_largest_placement_controls_shared_image_resolution(self):
        self.fixture(placements=(150, 900))
        shrink_pdf.compress(self.source, self.output)
        with pikepdf.open(self.output) as pdf:
            self.assertEqual(pdf.pages[0].Resources.XObject.Im.Width, 900)
            self.assertEqual(
                pdf.pages[0].Resources.XObject.Im.objgen,
                pdf.pages[1].Resources.XObject.Im.objgen,
            )

    def test_shared_mask_is_not_resized(self):
        self.fixture(shared_mask=True)
        shrink_pdf.compress(self.source, self.output)
        with pikepdf.open(self.output) as pdf:
            objects = pdf.pages[0].Resources.XObject
            self.assertEqual(objects.Im.Width, 900)
            self.assertEqual(objects.Other.Width, 900)
            self.assertEqual(objects.Im.SMask.Width, 900)
            self.assertEqual(objects.Im.SMask.objgen, objects.Other.SMask.objgen)

    def test_flat_color_artwork_stays_lossless(self):
        self.fixture(line_art=True)
        shrink_pdf.compress(self.source, self.output)
        with pikepdf.open(self.source) as a, pikepdf.open(self.output) as b:
            self.assertEqual(
                a.pages[0].Resources.XObject.Im.read_bytes(),
                b.pages[0].Resources.XObject.Im.read_bytes(),
            )

    def test_existing_output_is_preserved(self):
        self.fixture()
        self.output.write_bytes(b"existing output")
        with self.assertRaises(FileExistsError):
            shrink_pdf.compress(self.source, self.output)
        self.assertEqual(self.output.read_bytes(), b"existing output")

    def test_decode_arrays_are_left_intact(self):
        self.fixture()
        intermediate = Path(self.temp.name) / "decoded.pdf"
        with pikepdf.open(self.source) as pdf:
            pdf.pages[0].Resources.XObject.Im.Decode = [1, 0, 1, 0, 1, 0]
            pdf.save(intermediate)
        shrink_pdf.compress(intermediate, self.output)
        with pikepdf.open(intermediate) as a, pikepdf.open(self.output) as b:
            before, after = (p.pages[0].Resources.XObject.Im for p in (a, b))
            self.assertEqual(before.read_bytes(), after.read_bytes())
            self.assertEqual(list(before.Decode), list(after.Decode))

    def test_already_small_pdf_never_grows(self):
        with pikepdf.Pdf.new() as pdf:
            pdf.add_blank_page()
            pdf.save(self.source, object_stream_mode=pikepdf.ObjectStreamMode.generate)
        shrink_pdf.compress(self.source, self.output)
        self.assertLessEqual(self.output.stat().st_size, self.source.stat().st_size)

    def test_failed_input_leaves_no_output(self):
        self.source.write_bytes(b"not a pdf")
        with self.assertRaises(pymupdf.FileDataError):
            shrink_pdf.compress(self.source, self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
