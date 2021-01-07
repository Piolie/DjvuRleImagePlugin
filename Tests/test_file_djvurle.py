import pytest
from io import BytesIO
from PIL import Image, UnidentifiedImageError

import sys
sys.path.insert(0, "..")
import DjvuRleImagePlugin  # noqa: E402


def assert_image_equal(a, b):
    """Helper function to compare two images."""
    assert a.mode == b.mode
    assert a.size == b.size
    if a.tobytes() != b.tobytes():
        assert False, msg or "got different content"


# sample djvurle streams made with the Netpbm tools
TEST_FILE_BITONAL = "images/hopper_1.djvurle"
TEST_FILE_COLOR = "images/hopper_RGBA.djvurle"


def test_sanity():
    with Image.open(TEST_FILE_BITONAL) as im:
        im.load()
        assert im.mode == "1"
        assert im.size == (128, 128)
        assert im.format, "DJVURLE"
        assert im.get_format_mimetype() == "image/x-djvurle-bitmap"

    with Image.open(TEST_FILE_COLOR) as im:
        im.load()
        assert im.mode == "RGBA"
        assert im.size == (128, 128)
        assert im.format, "DJVURLE"
        assert im.get_format_mimetype() == "image/x-djvurle-pixmap"

def test_bad_magic():
    with pytest.raises(SyntaxError):
        DjvuRleImagePlugin.DjvuRleImageFile(fp=BytesIO(b'R45'))


def test_bitonal_modes(tmp_path):
    images = ["hopper_1"]
    for image in images:
        with Image.open("images/" + image + ".png") as im:
            f = str(tmp_path / "temp.djvurle")
            im.save(f)

            with Image.open(f) as reloaded:
                assert_image_equal(im, reloaded)


def test_color_modes(tmp_path):
    images = ["hopper_L", "hopper_P", "hopper_RGB", "hopper_RGBA"]
    for image in images:
        with Image.open("images/" + image + ".png") as im:
            f = str(tmp_path / "temp.djvurle")
            im = im.convert(mode="RGBA")
            im.save(f)

            with Image.open(f) as reloaded:
                assert_image_equal(im, reloaded)


def test_partial_transparency(tmp_path):
    with Image.open("images/hopper_RGBA_partial.png") as im:
        f = str(tmp_path / "temp.djvurle")
        im.save(f)

    with Image.open("images/hopper_RGBA.png") as im:
        with Image.open(f) as reloaded:
            assert_image_equal(im, reloaded)


def test_header_with_comments(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"R4 #comment\n#comment\r12#comment\r8\n128#comment\n")

    with Image.open(path) as im:
        assert im.size == (128, 128)


def test_nondecimal_header(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"R4\n128\x00")

    with pytest.raises(ValueError):
        Image.open(path)


def test_truncated_header(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"R4\n128")

    with pytest.raises(ValueError):
        Image.open(path)


def test_too_many_colors_decoder(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"R6\n128\n128\n4081")

    with pytest.raises(ValueError):
        Image.open(path)


def test_too_many_colors_encoder(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with Image.open("images/hopper.png") as im:
        with pytest.raises(ValueError):
            im.save(path)


def test_truncated_palette(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"R6\n128\n128\n64\n\x00\x00\x00")

    with pytest.raises(OSError):
        Image.open(path).load()


def test_truncated_data_bitonal(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"R4\n128\n128\n\x00")

    with pytest.raises(OSError):
        Image.open(path).load()


def test_truncated_data_color(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"R6\n128\n128\n1\n\x00\x00\x00\xFF")

    with pytest.raises(OSError):
        Image.open(path).load()


def test_run_too_long_bitonal(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"R4\n128\n128\n\xBF")

    with pytest.raises(ValueError):
        Image.open(path).load()


def test_run_too_long_color(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"R6\n128\n128\n1\n\x00\x00\x00\x00\x0f\xff\xff")

    with pytest.raises(ValueError):
        Image.open(path).load()


def test_color_index_too_large(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"R6\n128\n128\n1\n\x00\x00\x00\xff\x1f\xff\xff")

    with pytest.raises(ValueError):
        Image.open(path).load()


def test_extra_data_bitonal(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"R4\n1\n1\n\x01\x00")

    with pytest.raises(OSError):
        Image.open(path).load()


def test_extra_data_color(tmp_path):
    path = str(tmp_path / "temp.djvurle")
    with open(path, "wb") as f:
        f.write(b"R6\n1\n1\n1\n\x00\x00\x00\x00\x00\x00\x01\x00")

    with pytest.raises(OSError):
        Image.open(path).load()
