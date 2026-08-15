import tempfile
import unittest
from pathlib import Path

from PIL import Image

from photo_selector import (
    discover_images,
    export_destination_matches_source_folder,
    export_image,
    export_stem,
    natural_sort_key,
    prepare_for_export,
    unique_output_path,
)


class PhotoSelectorTests(unittest.TestCase):
    def test_natural_sort(self) -> None:
        paths = [Path("photo10.jpg"), Path("photo2.jpg"), Path("photo1.jpg")]
        self.assertEqual(
            [path.name for path in sorted(paths, key=natural_sort_key)],
            ["photo1.jpg", "photo2.jpg", "photo10.jpg"],
        )

    def test_discover_images_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            nested = root / "nested"
            nested.mkdir()
            Image.new("RGB", (8, 8), "red").save(root / "a.jpg")
            Image.new("RGBA", (8, 8), "blue").save(nested / "b.png")
            (root / "notes.txt").write_text("not an image", encoding="utf-8")
            self.assertEqual(len(discover_images(root)), 2)

    def test_unique_output_path_does_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "photo.jpg").write_bytes(b"existing")
            (root / "photo_2.jpg").write_bytes(b"existing")
            self.assertEqual(unique_output_path(root, "photo", ".jpg").name, "photo_3.jpg")

    def test_export_stem_supports_original_and_sequence_names(self) -> None:
        source = Path("holiday-photo.jpg")
        self.assertEqual(export_stem(source, 1, "保留原文件名"), "holiday-photo")
        self.assertEqual(export_stem(source, 1, "顺序编号 001..."), "001")
        self.assertEqual(export_stem(source, 12, "顺序编号 001..."), "012")
        self.assertEqual(export_stem(source, 1000, "顺序编号 001..."), "1000")

    def test_export_destination_cannot_be_source_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "output"
            source = root / "source.jpg"
            self.assertTrue(export_destination_matches_source_folder(root, [source]))
            self.assertFalse(export_destination_matches_source_folder(output, [source]))

    def test_transparent_image_is_flattened_for_jpeg(self) -> None:
        image = Image.new("RGBA", (4, 4), (255, 0, 0, 0))
        prepared = prepare_for_export(image, "JPEG")
        self.assertEqual(prepared.mode, "RGB")
        self.assertEqual(prepared.getpixel((0, 0)), (255, 255, 255))

    def test_cmyk_image_is_converted_for_png(self) -> None:
        image = Image.new("CMYK", (4, 4), (0, 20, 50, 10))
        self.assertEqual(prepare_for_export(image, "PNG").mode, "RGB")

    def test_export_png_as_jpeg(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.png"
            destination = root / "output.jpg"
            Image.new("RGBA", (24, 18), (20, 80, 160, 180)).save(source)
            source_bytes = source.read_bytes()
            export_image(source, destination, "JPEG", 90)
            self.assertEqual(source.read_bytes(), source_bytes)
            with Image.open(destination) as result:
                self.assertEqual(result.format, "JPEG")
                self.assertEqual(result.size, (24, 18))


if __name__ == "__main__":
    unittest.main()
