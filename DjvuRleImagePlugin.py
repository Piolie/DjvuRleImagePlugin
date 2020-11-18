#
# The Python Imaging Library.
# $Id$
#
# DjVu RLE support for Pillow
#
# History:
#       2020-11-18     Created
#
# Copyright (c) Piolie.
#
# See the README file for information on usage and redistribution.
#

"""
A Pillow plugin to handle RLE encoded images as specified in the DjVuLibre docs.
"""

from io import BytesIO
from PIL import Image, ImageFile

#
# --------------------------------------------------------------------

WHITESPACE = b"\x20\x09\x0A\x0D"  # whitespace can be: space, tab, CR, or LF

MODES = {  # image modes for the two formats
    b"R4": "1",  # bitonal
    b"R6": "RGBA",  # paletted with transparency
}


def _accept(prefix):
    return prefix[0:1] == b"R" and prefix[1] in b"46"


class DjvuRleImageFile(ImageFile.ImageFile):
    """
    Basic class to handle DjVu RLE.
    """

    format = "DJVURLE"
    format_description = "DjVu RLE image"

    def _token(self, s=b""):
        while True:  # read until next whitespace
            c = self.fp.read(1)
            if not c or c in WHITESPACE:
                break
            if not b"\x2F" < c < b"\x3A":
                raise ValueError("Non-ASCII-decimal token found")
            s = s + c
        return s

    def _open(self):
        # read magic number
        s = self.fp.read(1)
        if s != b"R":
            raise ValueError("Not a DJVURLE file")
        magic_number = self._token(s)
        self.mode = MODES[magic_number]

        self.custom_mimetype = {
            b"R4": "image/x-djvurle-bitmap",
            b"R6": "image/x-djvurle-pixmap",
        }.get(magic_number)

        for ix in range(3):
            while True:
                while True:
                    s = self.fp.read(1)
                    if s not in WHITESPACE:
                        break
                    if s == b"":
                        raise ValueError("Truncated file")
                if s != b"#":
                    break
                s = self.fp.readline()
            s = int(self._token(s))
            if ix == 0:  # s is the x size
                xsize = s
            elif ix == 1:  # s is the y size
                ysize = s
                if self.mode == "1":
                    number_of_colors = 0  # bitonal decoder ignores this value
                    break
            elif ix == 2:  # s is the number of colors
                if s > 0xFF0:  # check palette size
                    raise ValueError(f"Too many colors for palette: {s}")
                number_of_colors = s

        self._size = xsize, ysize
        self.tile = [
            (
                "DJVURLE",  # decoder
                (0, 0) + self._size,  # region
                self.fp.tell(),  # offset to image data
                number_of_colors,  # parameters for decoder
            )
        ]


class DjvuRleDecoder(ImageFile.PyDecoder):
    """
    Class to decode DjVu RLE.
    """

    def decode(self, buffer):
        BITONAL_MASK = 0b0011111111111111
        COLOR_MASK = 0b00000000000011111111111111111111

        data = bytearray()  # much faster than: data = b""
        xsize = self.state.xsize  # row length
        ysize = self.state.ysize  # number of rows
        size = xsize * ysize  # total number of pixels
        buffer = BytesIO(buffer)

        def decode_bitonal(buffer):
            nonlocal data
            total_length = 0
            while total_length < size:
                white_run = True  # each line starts with a white run
                line_length = 0
                while line_length < xsize:
                    first_byte = buffer.read(1)
                    if first_byte > b"\xBF":
                        second_byte = buffer.read(1)
                        run_length = (
                            int.from_bytes(first_byte + second_byte, byteorder="big")
                            & BITONAL_MASK  # make the two MSBs zero
                        )
                    else:
                        run_length = ord(first_byte)

                    line_length += run_length
                    if line_length > xsize:  # check line length
                        raise ValueError(
                            f"Run too long in line: {total_length//xsize + 1}"
                        )
                    data += (b"\xFF" * white_run or b"\x00") * run_length
                    white_run = not white_run
                total_length += line_length
            if buffer.read(1) != b"":
                raise ValueError("There are extra data at the end of the file")
            self.set_as_raw(bytes(data), rawmode="1;8")

        def decode_RGBA(buffer):
            nonlocal data
            num_of_colors = self.args[0]
            palette = [b"0000"] * num_of_colors  # initialize palette
            for n in range(num_of_colors):  # load palette colors
                palette[n] = buffer.read(3)
            total_length = 0
            while total_length < size:
                line_length = 0
                while line_length < xsize:
                    run = int.from_bytes(buffer.read(4), byteorder="big")
                    color_index = run >> 20  # upper twelve bits (32 - 20)
                    run_length = run & COLOR_MASK  # lower twenty bits
                    transparent = color_index == 0xFFF
                    if color_index > num_of_colors and not transparent:
                        raise ValueError(
                            "Color index greater than 0xFF0 in line {total_length//xsize + 1}"
                        )
                    line_length += run_length
                    if line_length > xsize:
                        raise ValueError(
                            f"Run too long in line: {total_length//xsize + 1}"
                        )
                    data += (
                        b"000\x00" * transparent or palette[color_index] + b"\xFF"
                    ) * run_length
                total_length += line_length
            if buffer.read(1) != b"":
                raise ValueError("There are extra data at the end of the file")
            self.set_as_raw(bytes(data), rawmode="RGBA")

        if self.mode == "1":
            decode_bitonal(buffer)
        elif self.mode == "RGBA":
            decode_RGBA(buffer)
        else:
            raise ValueError(f"Wrong image mode: {self.mode}")

        return (-1, 0)


class DjvuRleEncoder(ImageFile.PyDecoder):
    """
    Yet unimplemented encoding class due to lack of documentation.
    """

    pass


def _save(im, fp, filename):
    """
    Yet unimplemented saving function due to lack of documentation.
    """
    pass


# --------------------------------------------------------------------


Image.register_open(DjvuRleImageFile.format, DjvuRleImageFile, _accept)
Image.register_extensions(DjvuRleImageFile.format, [".rle", ".djvurle"])
Image.register_mime(DjvuRleImageFile.format, "image/x-djvurle-anymap")
Image.register_decoder(DjvuRleImageFile.format, DjvuRleDecoder)
Image.register_encoder(DjvuRleImageFile.format, DjvuRleEncoder)
