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

# from io import BytesIO
from PIL import Image, ImageFile

#
# --------------------------------------------------------------------

WHITESPACE = b" \t\r\n"  # whitespace can be: space, tab, CR, or LF

MODES = {  # image modes for the two formats
    b"R4": "1",  # bitonal
    b"R6": "RGBA",  # paletted with transparency
}


def _accept(prefix):
    return prefix[0:1] == b"R" and prefix[1] in b"46"


class DjvuRleImageFile(ImageFile.ImageFile):
    """
    Class to identify DjVu RLE files.
    """

    format = "DJVURLE"
    format_description = "DjVu RLE image"

    def _read_token(self, s=b""):
        """
        Read one token and detect errors in format.
        """

        def _is_decimal_ascii(c):  # verifies ASCII decimal
            return b"\x2F" < c < b"\x3A"

        def _ignore_line():  # ignores line; line ends with CR _xor_ LF
            while True:
                c = self.fp.read(1)
                if c == b"":  # reached EOF
                    raise EOFError("Reached EOF while reading header")
                if c in b"\r\n":
                    break

        while True:  # read until non-whitespace is found
            c = self.fp.read(1)
            if c == b"":  # reached EOF
                raise EOFError("Reached EOF while reading header")
            if _is_decimal_ascii(c):  # found what we were looking for
                break
            if c == b"#":  # found comment line, ignore it
                _ignore_line()
                continue
            if c in WHITESPACE:  # found whitespace, ignore it
                continue
            raise ValueError("Non-decimal-ASCII found in header")

        s = s + c

        while True:  # read until next whitespace
            c = self.fp.read(1)
            if _is_decimal_ascii(c):  # append decimal
                s = s + c
                continue
            if c in WHITESPACE:  # token ended
                break
            if c == b"#":
                _ignore_line()
                continue
            else:
                raise ValueError("Non-decimal-ASCII found in header")

        return s

    def _open(self):
        """
        Load image parameters.
        """
        # read magic number
        s = self.fp.read(1)
        if s != b"R":  # TODO: redundant? (already have _accept)
            raise ValueError("Not a DJVURLE file")
        magic_number = self._read_token(s)
        self.mode = MODES[magic_number]

        self.custom_mimetype = {
            b"R4": "image/x-djvurle-bitmap",
            b"R6": "image/x-djvurle-pixmap",
        }[magic_number]

        for ix in range(3):
            token = int(self._read_token())
            if ix == 0:  # token is the x size
                xsize = token
            elif ix == 1:  # token is the y size
                ysize = token
                if self.mode == "1":
                    number_of_colors = 0  # bitonal decoder ignores this value
                    break
            elif ix == 2:  # token is the number of colors
                if token > 4080:  # check palette size
                    raise ValueError(
                        f"Too many colors: {token}; reduce to 4080 or less"
                    )
                number_of_colors = token

        self._size = xsize, ysize
        self.tile = [
            (
                "DJVURLE",  # decoder
                (0, 0) + self._size,  # region: whole image
                self.fp.tell(),  # offset to image data
                number_of_colors,  # parameters for decoder
            )
        ]


class DjvuRleDecoder(ImageFile.PyDecoder):
    """
    Class to decode DjVu RLE images.
    """

    _pulls_fd = True  # TODO: experimental; gotta learn how to do it with buffer

    def decode(self, buffer):
        xsize = self.state.xsize  # row length
        ysize = self.state.ysize  # number of rows
        size = xsize * ysize  # total number of pixels
        # if using buffer;
        # TODO: not sure about the performance impact of wrapping in BytesIO...
        # buffer = BytesIO(buffer)
        buffer = self.fd  # if using _pulls_fd

        def decode_bitonal():
            BITONAL_MASK = 0x3FFF
            data = bytearray()  # much faster than: data = bytes()

            total_length = 0
            while total_length < size:
                is_white_run = True  # each line starts with a white run
                line_length = 0
                while line_length < xsize:
                    first_byte = buffer.read(1)
                    if first_byte == b"":
                        raise EOFError("Reached EOF while reading image data")
                    if first_byte > b"\xBF":  # two-byte run
                        second_byte = buffer.read(1)
                        if second_byte == b"":
                            raise EOFError("Reached EOF while reading image data")
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
                    data += (b"\xFF" * is_white_run or b"\x00") * run_length
                    is_white_run = not is_white_run
                total_length += line_length
            if buffer.read() != b"":
                raise EOFError("There are extra data at the end of the file")
            self.set_as_raw(bytes(data), rawmode="1;8")

        def decode_rgba():
            COLOR_MASK = 0xFFFFF
            data = bytearray()

            number_of_colors = self.args[0]
            palette = {
                n: b"" for n in range(number_of_colors)
            }  # initialize palette
            for n in range(number_of_colors):  # load colors in palette
                color = buffer.read(3)
                if len(color) < 3:
                    raise EOFError("Reached EOF while reading image palette")
                palette[n] = color
            total_length = 0
            while total_length < size:
                line_length = 0
                while line_length < xsize:
                    raw_run = buffer.read(4)
                    if len(raw_run) < 4:
                        raise EOFError("Reached EOF while reading image data")
                    run = int.from_bytes(raw_run, byteorder="big")
                    color_index = run >> 20  # upper twelve bits (32 - 20)
                    run_length = run & COLOR_MASK  # lower twenty bits
                    is_transparent = color_index == 0xFFF
                    if color_index > number_of_colors and not is_transparent:
                        raise ValueError(
                            f"Color index greater than {number_of_colors} in line {total_length//xsize + 1}"
                        )
                    line_length += run_length
                    if line_length > xsize:
                        raise ValueError(
                            f"Run too long in line: {total_length//xsize + 1}"
                        )
                    data += (
                        b"\x00\x00\x00\x00" * is_transparent
                        or palette[color_index] + b"\xFF"
                    ) * run_length
                total_length += line_length
            if buffer.read() != b"":
                raise ValueError("There are extra data at the end of the file")
            self.set_as_raw(bytes(data), rawmode="RGBA")

        if self.mode == "1":
            decode_bitonal()
        elif self.mode == "RGBA":
            decode_rgba()

        return -1, 0


# --------------------------------------------------------------------


Image.register_open(DjvuRleImageFile.format, DjvuRleImageFile, _accept)
Image.register_extensions(DjvuRleImageFile.format, [".rle", ".djvurle"])
Image.register_mime(DjvuRleImageFile.format, "image/x-djvurle-anymap")
Image.register_decoder(DjvuRleImageFile.format, DjvuRleDecoder)
